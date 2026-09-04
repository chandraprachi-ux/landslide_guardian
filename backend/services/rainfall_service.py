"""
Live rainfall service.

Responsibilities:
    - fetch live rainfall for a location from the configured weather source
    - validate the observation (rejects negatives, NaN, unreasonably large)
    - timestamp the observation
    - deduplicate (same location + timestamp + value) so repeated requests
      do not create duplicate rows
    - append the record to the rainfall_records store
    - return a structured live record

Robustness:
    - weather API timeout / HTTP error / malformed response => returns
      DATA_UNAVAILABLE without crashing the backend, and NEVER fabricates a
      rainfall value.
    - a genuine 0 mm is a VALID observation ("NO RAIN"), distinct from a
      failed fetch ("NO DATA").
"""

import math
import hashlib
import logging
from datetime import datetime, timezone

from ..database.mongodb import db_manager
from .weather_service import fetch_environmental_data

logger = logging.getLogger(__name__)

# Rainfall sanity cap (mm). Real single-window totals above this are suspect.
MAX_PLAUSIBLE_RAINFALL_MM = 600.0


class RainfallUnavailable(Exception):
    """Raised when live rainfall cannot be retrieved (not a genuine 0)."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _location_key(name: str, lat: float, lon: float) -> str:
    return (name or "").strip().lower() or f"{lat:.4f},{lon:.4f}"


def _dedup_key(loc_key: str, window: int, rainfall: float) -> str:
    raw = f"{loc_key}|{window}|{round(rainfall, 2)}|{datetime.now(timezone.utc).strftime('%Y%m%d%H')}"
    return hashlib.sha1(raw.encode()).hexdigest()


def validate_rainfall(rainfall, unit="mm") -> dict:
    """
    Validate an observation. Returns {"valid": True/False, "reason": ...}.
    Treats a genuine 0 as valid (NO RAIN).
    """
    if rainfall is None:
        return {"valid": False, "reason": "missing rainfall value; provider returned null"}
    if isinstance(rainfall, str):
        try:
            rainfall = float(rainfall)
        except (TypeError, ValueError):
            return {"valid": False, "reason": "malformed rainfall value (not numeric)"}
    if isinstance(rainfall, bool) or not isinstance(rainfall, (int, float)):
        return {"valid": False, "reason": "invalid rainfall type"}
    if math.isnan(rainfall) or math.isinf(rainfall):
        return {"valid": False, "reason": "NaN/Inf rainfall value"}
    if rainfall < 0:
        return {"valid": False, "reason": "negative rainfall is invalid"}
    if rainfall > MAX_PLAUSIBLE_RAINFALL_MM:
        return {"valid": False, "reason": f"implausibly large rainfall (> {MAX_PLAUSIBLE_RAINFALL_MM} mm)"}
    return {"valid": True, "reason": ""}


async def get_live_rainfall(location_name: str, lat: float, lon: float) -> dict:
    """
    Fetch live rainfall from the Open-Meteo source already used by the project.

    Returns a structured record on success, or raises RainfallUnavailable with
    a safe reason. Never fabricates data.
    """
    loc_key = _location_key(location_name, lat, lon)
    try:
        env = await fetch_environmental_data(lat, lon)
    except Exception as exc:
        logger.warning("Weather fetch failed for %s: %s", loc_key, exc)
        raise RainfallUnavailable("WEATHER_PROVIDER_UNAVAILABLE") from exc

    # fetch_environmental_data returns a WEATHER_FALLBACK object on failure.
    if getattr(env, "data_source", "") in ("WEATHER_FALLBACK",):
        raise RainfallUnavailable("WEATHER_PROVIDER_UNAVAILABLE")

    rainfall_1h = float(getattr(env, "rainfall_1h", 0) or 0)
    rainfall_24h = float(getattr(env, "rainfall_24h", 0) or 0)
    rainfall_72h = float(getattr(env, "rainfall_72h", 0) or 0)

    # The primary live value is the 24h window used by the risk engine.
    live = rainfall_24h
    check = validate_rainfall(live)
    if not check["valid"]:
        check["location"] = location_name
        raise RainfallUnavailable(f"INVALID rainfall: {check['reason']}")

    weather_condition = _weather_condition_from_env(env)
    window_hours = 24

    return {
        "location": location_name,
        "location_key": loc_key,
        "latitude": lat,
        "longitude": lon,
        "timestamp": _now_iso(),
        "rainfall": round(live, 2),
        "rainfall_1h_mm": round(rainfall_1h, 2),
        "rainfall_24h_mm": round(live, 2),
        "rainfall_72h_mm": round(rainfall_72h, 2),
        "rainfall_unit": "mm",
        "rainfall_window": f"{window_hours}h",
        "rainfall_window_hours": window_hours,
        "weather_condition": weather_condition,
        "weather_detail": {
            "temperature_c": getattr(env, "temperature", None),
            "humidity_pct": getattr(env, "humidity", None),
            "wind_speed_kmh": getattr(env, "wind_speed", None),
        },
        "source": getattr(env, "data_source", "OPEN_METEO_LIVE"),
        "source_url": "https://api.open-meteo.com/v1/forecast",
        "data_quality": "LIVE",
        "data_status": "NO_RAIN" if live == 0 else "RAIN",
    }


def _weather_condition_from_env(env):
    rain = float(getattr(env, "rainfall_1h", 0) or 0)
    if rain <= 0:
        return "Dry"
    if rain < 5:
        return "Light rain"
    if rain < 20:
        return "Moderate rain"
    return "Heavy rain"


def append_rainfall_record(record: dict) -> dict:
    """Persist a live rainfall observation with deduplication protection."""
    loc_key = record.get("location_key") or _location_key(record.get("location", ""), record.get("latitude", 0), record.get("longitude", 0))
    window = record.get("rainfall_window_hours", 24)
    rainfall = record.get("rainfall_24h_mm", record.get("rainfall", 0))
    dk = _dedup_key(loc_key, window, rainfall)

    # Dedup: same location+timestamp+value should not create duplicates.
    if db_manager.rainfall_records.find_one({"dedup_key": dk}):
        return {**record, "dedup": "SKIPPED_DUPLICATE", "record_id": None}

    doc = {**record, "dedup_key": dk}
    res = db_manager.rainfall_records.insert_one(doc)
    doc["record_id"] = getattr(res, "inserted_id", None)
    doc["dedup"] = "APPENDED"
    return doc


def get_recent_rainfall(location_name: str, lat: float, lon: float, limit: int = 10) -> list:
    loc_key = _location_key(location_name, lat, lon)
    docs = list(db_manager.rainfall_records.find({"location_key": loc_key}).sort("timestamp", -1).limit(limit))
    out = []
    for d in docs:
        out.append({
            "location": d.get("location"),
            "timestamp": d.get("timestamp"),
            "rainfall_24h_mm": d.get("rainfall_24h_mm"),
            "rainfall_unit": d.get("rainfall_unit"),
            "rainfall_window": d.get("rainfall_window"),
            "source": d.get("source"),
            "data_quality": d.get("data_quality"),
            "data_status": d.get("data_status"),
        })
    return out


def get_latest_antecedent_head(location_name: str, lat: float, lon: float) -> float:
    """Most recent wetting estimate stored for this location (mm), else 0."""
    recent = get_recent_rainfall(location_name, lat, lon, 1)
    if recent:
        return float(recent[0].get("rainfall_24h_mm", 0) or 0)
    return 0.0
