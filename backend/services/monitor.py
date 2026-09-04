import asyncio
import logging
import os
from datetime import datetime, timezone

from ..database.mongodb import db_manager
from .notification_service import dispatch_email_sos
from .risk_service import calculate_risk_assessment
from .terrain_service import NER_COORDS

logger = logging.getLogger(__name__)

# Friendly NER labels matching the frontend DEMO_LOCATIONS / citizen registrations.
NER_LABELS = {
    "gangtok": "Gangtok, Sikkim",
    "shillong": "Shillong, Meghalaya",
    "aizawl": "Aizawl, Mizoram",
    "kohima": "Kohima, Nagaland",
    "itanagar": "Itanagar, Arunachal Pradesh",
    "guwahati": "Guwahati, Assam",
    "imphal": "Imphal, Manipur",
    "agartala": "Agartala, Tripura",
}

# Default monitoring interval. Override via env var MONITOR_INTERVAL_MINUTES.
MONITOR_INTERVAL_SECONDS = 60 * int(os.getenv("MONITOR_INTERVAL_MINUTES", "15"))

# How long we suppress a second automatic email to the same location during an
# ongoing event (avoids spamming residents on every scheduler tick).
DISPATCH_COOLDOWN_SECONDS = 60 * int(os.getenv("SOS_COOLDOWN_MINUTES", "60"))

_monitor_enabled = True
_last_run = None
_run_status = None
_running = False


_hotspots = []
_monitored_sublocations_cache = {}


def get_monitoring_state() -> dict:
    """Public snapshot of the background monitoring loop state."""
    return {
        "enabled": _monitor_enabled,
        "running": _running,
        "interval_seconds": MONITOR_INTERVAL_SECONDS,
        "dispatch_cooldown_seconds": DISPATCH_COOLDOWN_SECONDS,
        "last_run": _last_run,
        "status": _run_status,
        "locations": list(NER_LABELS.values()),
        "hotspots_count": len(_hotspots),
        "hotspots": _hotspots,
    }


def get_active_hotspots() -> list:
    """Return currently detected emerging landslide hotspots."""
    return list(_hotspots)


def set_monitor_enabled(enabled: bool):
    """Allow the admin to pause/resume automatic monitoring (config endpoint)."""
    global _monitor_enabled
    _monitor_enabled = bool(enabled)
    return _monitor_enabled


def _iter_locations():
    """Yield (label, lat, lon, is_primary) for monitored NER locations and key sub-locations."""
    # 1. 8 Primary Regional Anchors
    for key, coords in NER_COORDS.items():
        label = NER_LABELS.get(key, key.title())
        yield label, coords[0], coords[1], True

    # 2. Key Sub-locations across the regions
    from .geo_hierarchy import NER_SUBLOCATIONS
    for sub in NER_SUBLOCATIONS:
        yield f"{sub['name']}, {sub['state']}", sub["lat"], sub["lon"], False


def _get_high_threshold(result):
    """Extract the 'high' pore-pressure threshold from a risk result."""
    t = getattr(result, "thresholds", None) or {}
    return t.get("pore_pressure_high_kpa")


async def run_monitor_cycle(force: bool = False) -> dict:
    """
    Run one full monitoring pass with controlled concurrency:
    recompute risk across regional anchors and key sublocations,
    detect emerging hotspots, and let the automatic SOS dispatcher
    email residents on HIGH/CRITICAL events for that specific locality.
    """
    global _last_run, _run_status, _running, _hotspots, _monitored_sublocations_cache
    if _running and not force:
        return {"status": "ALREADY_RUNNING", "note": "A monitoring cycle is already in progress."}

    _running = True
    started = datetime.now(timezone.utc).isoformat()
    results = []
    detected_hotspots = []
    sem = asyncio.Semaphore(3)  # Maximum 3 concurrent evaluation tasks

    async def _eval_one(label, lat, lon, is_primary):
        async with sem:
            try:
                # Small stagger to respect API providers
                await asyncio.sleep(0.15)
                res = await calculate_risk_assessment(label, lat, lon)
                prev_entry = _monitored_sublocations_cache.get(label)
                prev_level = prev_entry.get("risk_level") if prev_entry else "LOW"
                prev_score = prev_entry.get("risk_score") if prev_entry else 0

                entry = {
                    "location": res.location,
                    "region": res.region_label,
                    "region_id": res.region,
                    "latitude": res.latitude,
                    "longitude": res.longitude,
                    "risk_score": res.risk_score,
                    "risk_level": res.risk_level,
                    "rainfall": res.rainfall_details.get("rainfall_24h_mm", res.environmental_data.rainfall_24h),
                    "pore_pressure": res.pore_pressure_details.get("value_kpa"),
                    "threshold": _get_high_threshold(res),
                    "data_quality": res.data_quality,
                    "data_status": res.data_status,
                    "is_primary": is_primary,
                    "why_explanation": getattr(res, "why_explanation", []),
                    "timestamp": res.timestamp,
                }
                _monitored_sublocations_cache[label] = entry

                # Emerging Hotspot Detection:
                # Local area transitions into HIGH/CRITICAL or exhibits significant surge
                if res.risk_level in ("HIGH", "CRITICAL"):
                    is_emerging = (prev_level in ("LOW", "MODERATE")) or (res.risk_score - prev_score >= 15)
                    detected_hotspots.append({
                        "location": res.location,
                        "region": res.region_label,
                        "latitude": res.latitude,
                        "longitude": res.longitude,
                        "risk_level": res.risk_level,
                        "risk_score": res.risk_score,
                        "rainfall_24h": entry["rainfall"],
                        "emerging": is_emerging,
                        "detected_at": datetime.now(timezone.utc).isoformat(),
                        "alert_level": "CRITICAL" if res.risk_level == "CRITICAL" else "WARNING",
                        "summary": f"Emerging hotspot: {res.location} has reached {res.risk_level} landslide risk ({res.risk_score}%)."
                    })
                return entry
            except Exception as exc:
                logger.exception("Monitor cycle failed for %s", label)
                return {"location": label, "error": str(exc), "is_primary": is_primary}

    try:
        tasks = [_eval_one(label, lat, lon, is_primary) for label, lat, lon, is_primary in _iter_locations()]
        raw_results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in raw_results:
            if isinstance(r, dict):
                results.append(r)
            elif isinstance(r, Exception):
                results.append({"error": str(r)})

        _hotspots = detected_hotspots
        _last_run = started
        _run_status = {
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "locations_checked": len(results),
            "high_or_critical": [r for r in results if r.get("risk_level") in ("HIGH", "CRITICAL")],
            "hotspots_count": len(_hotspots),
            "data_unavailable": [r for r in results if r.get("data_quality") == "DATA_UNAVAILABLE"],
        }
        return {
            "status": "COMPLETED",
            "started_at": started,
            "locations_checked": len(results),
            "hotspots": _hotspots,
            "results": results,
        }
    finally:
        _running = False


async def background_monitor_loop():
    """Periodically refresh risk for all locations and auto-dispatch SOS."""
    logger.info("Automatic monitoring loop started (every %ss).", MONITOR_INTERVAL_SECONDS)
    while True:
        if _monitor_enabled:
            try:
                await run_monitor_cycle()
            except Exception:
                logger.exception("Background monitoring cycle crashed; will retry next tick.")
        await asyncio.sleep(MONITOR_INTERVAL_SECONDS)


# ---------------------------------------------------------------------------
# Automatic SOS dispatch (shared by background monitoring and manual predicts)
# ---------------------------------------------------------------------------

def _last_dispatch_time(location_key: str):
    """Most recent automatic dispatch timestamp for a location (from notification log)."""
    doc = db_manager.notification_log.find_one(
        {"location_key": location_key, "kind": "AUTO_SOS"},
        sort=[("timestamp", -1)],
    )
    if not doc:
        return None
    try:
        return datetime.fromisoformat(doc["timestamp"])
    except Exception:
        return None


def find_verified_recipients(location: str, region_id: str = ""):
    """Return strictly VERIFIED registered residents whose city/area, state, or region matches.
    Used by both the automatic dispatcher and the admin manual dispatch."""
    location_key = (location or "").strip().lower()
    region_id = (region_id or "").strip().lower()
    region_tokens = set(region_id.replace("_", " ").split()) if region_id else set()
    region_norm = region_id.replace("_", " ").lower()

    # Also extract state token from comma, e.g. "Gangtok, Sikkim" -> ["gangtok", "sikkim"]
    loc_parts = [p.strip().lower() for p in location_key.split(",") if p.strip()]

    users = list(db_manager.citizens.find())
    matched = []
    for u in users:
        # STRICT VERIFICATION: unverified emails are strictly omitted
        if u.get("email_verified") is not True:
            continue

        ul = (u.get("location") or u.get("region") or "").lower().strip()
        if not ul:
            continue

        # 1. Exact or substring match in either direction
        if location_key in ul or ul in location_key:
            matched.append(u)
            continue

        # 2. Part match (e.g. resident registered for "Sikkim" matches "Gangtok, Sikkim")
        if any(part in ul or ul in part for part in loc_parts):
            matched.append(u)
            continue

        # 3. Region ID tokens match
        if region_tokens and region_tokens.intersection(ul.split()):
            matched.append(u)
            continue

        # 4. Region normalised match
        if region_norm and (u.get("region") or "").lower().replace("_", " ").replace("-", " ") == region_norm:
            matched.append(u)
            continue

    return matched



def auto_dispatch(location: str, risk_score: int, risk_level: str,
                  recommendation: str = "", region_id: str = "",
                  rainfall: float = None, rainfall_window: str = "24h",
                  pore_pressure: float = None, threshold: float = None,
                  data_source: str = ""):
    """
    Automatically email all VERIFIED registered residents whose location matches
    the HIGH/CRITICAL region, respecting a per-location cooldown so residents
    are not spammed on every scheduler tick.
    """
    location_key = location.strip().lower()

    # Cooldown check: don't re-dispatch the same region too soon.
    last = _last_dispatch_time(location_key)
    now = datetime.now(timezone.utc)
    if last and (now - last).total_seconds() < DISPATCH_COOLDOWN_SECONDS:
        waited = int(DISPATCH_COOLDOWN_SECONDS - (now - last).total_seconds())
        return {
            "dispatched": False,
            "location": location,
            "reason": f"Within cooldown ({waited}s left) — residents already notified recently.",
        }

    matching = find_verified_recipients(location, region_id)

    # Build the SOS message with actual values (no fabricated science claims).
    src = data_source or "configured weather provider"
    pp_line = f"Estimated Pore Pressure: {pore_pressure} kPa" if pore_pressure is not None else "Estimated Pore Pressure: not available"
    th_line = f"Regional Threshold: {threshold} kPa" if threshold is not None else "Regional Threshold: regional config"
    rain_line = (f"Rainfall: {rainfall} mm ({rainfall_window})"
                 if rainfall is not None else "Rainfall: not available")
    region_line = f"Region: {region_id.upper()}" if region_id else f"Region: {location}"

    message = (
        f"LANDSLIDE GUARDIAN — EMERGENCY ALERT\n"
        f"{region_line}\n"
        f"Risk Level: {risk_level}\n"
        f"{rain_line}\n"
        f"{pp_line}\n"
        f"{th_line}\n"
        f"Detected At: {now.isoformat()}\n"
        f"Reason: Current monitored conditions have reached the configured "
        f"{risk_level}-risk threshold.\n"
        f"Source: {src}\n\n"
        "This is an automated landslide-risk warning. Move away from unstable "
        "slopes, drainage channels and cut slopes, and follow official "
        "evacuation guidance. It is an early-warning notification, not a "
        "confirmed landslide report."
    )

    # Persist an audit record regardless of SMTP configuration so the admin
    # console can show real-time automatic activity.
    if matching:
        dispatch = dispatch_email_sos(location, matching, message, risk_score, risk_level)
        status = dispatch.get("status")
        audit = {
            "kind": "AUTO_SOS",
            "location": location,
            "location_key": location_key,
            "region": region_id,
            "risk_score": risk_score,
            "risk_level": risk_level,
            "recipient_count": dispatch.get("recipient_count", len(matching)),
            "eligible_verified_count": len(matching),
            "status": status,
            "smtp_configured": dispatch.get("smtp_configured"),
            "message": message,
            "timestamp": now.isoformat(),
        }
        try:
            db_manager.notification_log.insert_one(audit)
        except Exception:
            logger.exception("Failed to log automatic dispatch.")
        return {
            "dispatched": True,
            "status": status,
            "location": location,
            "region": region_id,
            "risk_level": risk_level,
            "risk_score": risk_score,
            "recipient_count": dispatch.get("recipient_count", len(matching)),
        }

    # No verified recipients: still log an audit record so activity is visible.
    audit = {
        "kind": "AUTO_SOS",
        "location": location,
        "location_key": location_key,
        "region": region_id,
        "risk_score": risk_score,
        "risk_level": risk_level,
        "recipient_count": 0,
        "eligible_verified_count": 0,
        "status": "NO_VERIFIED_RECIPIENTS",
        "message": message,
        "timestamp": now.isoformat(),
    }
    try:
        db_manager.notification_log.insert_one(audit)
    except Exception:
        logger.exception("Failed to log automatic dispatch (no verified recipients).")
    return {
        "dispatched": False,
        "status": "NO_VERIFIED_RECIPIENTS",
        "location": location,
        "region": region_id,
        "risk_level": risk_level,
        "risk_score": risk_score,
        "recipient_count": 0,
        "note": "No EMAIL-VERIFIED residents registered for this region yet. Register and verify residents to enable automatic SOS email.",
    }
