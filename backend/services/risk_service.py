import logging
import math
from datetime import datetime, timezone

from ..database.mongodb import db_manager
from ..ml.predict import predict_landslide_probability
from ..models.schemas import EnvironmentalData, RiskResult, SensorInput, SensorSnapshot
from .pore_pressure import estimated_pore_pressure
from .region_config import get_region_config, get_region_for_location
from .rainfall_service import (
    RainfallUnavailable, append_rainfall_record, get_live_rainfall
)
from .terrain_service import (
    build_thresholds, calculate_factor_of_safety, get_full_terrain_info
)
from .weather_service import fetch_environmental_data

logger = logging.getLogger(__name__)


def classify_risk(score: float) -> tuple[int, str]:
    score_i = int(round(max(0.0, min(100.0, score))))
    if score_i >= 81:
        return score_i, "CRITICAL"
    if score_i >= 61:
        return score_i, "HIGH"
    if score_i >= 31:
        return score_i, "MODERATE"
    return score_i, "LOW"


def _criteria_status(value, high, critical=None):
    if critical is not None and value >= critical:
        return "CRITICAL"
    if value >= high:
        return "HIGH"
    return "NORMAL"


def _safe_float(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


async def calculate_risk_assessment(
    location_name: str, lat: float, lon: float,
    sensor_data: SensorInput | None = None,
    use_live_rainfall: bool = True,
) -> RiskResult:
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError("Invalid latitude/longitude.")
    location_name = location_name.strip() or f"Lat {lat:.4f}, Lon {lon:.4f}"

    # Resolve region and load regional config (Sikkim / Assam / etc.).
    region_id = get_region_for_location(location_name, lat, lon)
    region_cfg = get_region_config(region_id)

    terrain = get_full_terrain_info(location_name, lat, lon)
    thresholds = build_thresholds(terrain)          # city thresholds (UI compat)
    env: EnvironmentalData = await fetch_environmental_data(lat, lon)
    env.slope = terrain["slope_deg"]
    env.elevation = terrain["elevation_m"]
    env.aspect = terrain["aspect_deg"]
    env.ndvi = terrain["ndvi"]
    env.distance_to_road = terrain["distance_to_road_m"]

    soil = _safe_float(sensor_data.soil_moisture) if sensor_data and sensor_data.soil_moisture is not None else float(env.soil_moisture or 0)
    tilt = _safe_float(sensor_data.tilt_degrees) if sensor_data and sensor_data.tilt_degrees is not None else 0.0

    # ------------------------------------------------------------------
    # LIVE RAINFALL + ESTIMATED PORE PRESSURE
    # ------------------------------------------------------------------
    rainfall = None
    rainfall_72h = env.rainfall_72h or 0.0
    data_quality = "LIVE"
    data_status = ""
    data_source_label = getattr(env, "data_source", "OPEN_METEO_LIVE")
    rainfall_fetch_ok = True
    rainfall_details = {}
    pore_details = {}
    pore = None
    pore_type = "estimated"
    antecedent_head = 0.0
    notes = []

    if use_live_rainfall and not (sensor_data and sensor_data.rainfall_level_mm is not None):
        try:
            live = await get_live_rainfall(location_name, lat, lon)
            rainfall = _safe_float(live.get("rainfall_24h_mm"))
            rainfall_72h = _safe_float(live.get("rainfall_72h_mm"))
            data_source_label = live.get("source", data_source_label)
            data_status = live.get("data_status", "RAIN")   # NO_RAIN | RAIN
            rainfall_details = live
            # Append the observation (dedup-protected).
            try:
                append_rainfall_record(live)
            except Exception:
                logger.exception("Failed to append rainfall record for %s", location_name)
        except RainfallUnavailable as exc:
            rainfall = None
            data_quality = "DATA_UNAVAILABLE"
            data_status = "NO_DATA"
            rainfall_fetch_ok = False
            rainfall_details = {"error": str(exc)}
            notes.append("LIVE DATA UNAVAILABLE — weather provider could not be reached. No data shown; not declaring a risk based on missing data.")
        except Exception as exc:
            rainfall = None
            data_quality = "DATA_UNAVAILABLE"
            data_status = "NO_DATA"
            rainfall_fetch_ok = False
            rainfall_details = {"error": "unexpected"}
            logger.exception("Unexpected rainfall error for %s", location_name)
            notes.append("LIVE DATA UNAVAILABLE (unexpected error).")
    elif sensor_data and sensor_data.rainfall_level_mm is not None:
        rainfall = _safe_float(sensor_data.rainfall_level_mm)
        rainfall_details = {"source": "sensor/simulation", "rainfall_24h_mm": rainfall}
        data_status = "NO_RAIN" if rainfall == 0 else "RAIN"

    if env and getattr(env, "data_source", "") == "WEATHER_FALLBACK" and use_live_rainfall and rainfall is None:
        data_quality = "DATA_UNAVAILABLE"
        data_status = "NO_DATA"
        notes.append("Weather provider unavailable — marked DATA_UNAVAILABLE (not LOW, not CRITICAL).")

    # Estimated pore pressure from rainfall + site parameters (LIVE/SOFTWARE path).
    site = region_cfg["site"]
    infilt = site["infiltration"]
    pp_input = {
        "rainfall_24h_mm": _safe_float(rainfall) if rainfall is not None else 0.0,
        "rainfall_72h_mm": _safe_float(rainfall_72h),
        "soil_depth_m": site["soil_depth_m"],
        "porosity": site["porosity"],
        "antecedent_head_mm": antecedent_head,
        "drainage_constant_hours": infilt["drainage_constant_hours"],
        "max_saturation_rise": infilt["max_saturation_rise"],
    }
    pore_details = estimated_pore_pressure(**pp_input)
    pore = pore_details["value_kpa"]
    pore_type = "estimated"

    # If a real sensor supplied pore pressure, prefer it and label as measured.
    if sensor_data and sensor_data.pore_pressure_kpa is not None:
        pore = _safe_float(sensor_data.pore_pressure_kpa)
        pore_type = "measured"
        pore_details = {**pore_details, "pore_pressure_type": "measured",
                        "label": "MEASURED pore pressure (sensor/piezometer)."}

    soil = max(0.0, min(100.0, soil))

    # If rainfall is unavailable, use the env value as a last resort for the
    # feature vector ONLY when live failed, but keep data_status NO_DATA.
    if rainfall is None:
        rainfall = float(env.rainfall_24h or 0)

    env.soil_moisture = soil
    env.rainfall_24h = rainfall
    env.rainfall_72h = rainfall_72h
    env.pore_pressure_kpa = pore

    # Map all live environmental, geotechnical and sensor parameters into features
    # Antecedent rainfall index (7d estimation from 72h / 24h)
    antecedent_7d = max(rainfall_72h * 1.5, rainfall * 2.2) if rainfall_72h else rainfall * 2.0
    accel_val = 9.81
    if sensor_data and hasattr(sensor_data, "accel_z") and sensor_data.accel_z is not None:
        accel_val = float(sensor_data.accel_z)

    features = {
        "soil_moisture": soil,
        "soil_moisture_pct": soil,
        "water_pressure": pore,
        "pore_pressure_kpa": pore,
        "acceleration": accel_val,
        "tilt_angle": tilt,
        "tilt_deg": tilt,
        "temperature": float(getattr(env, "temperature", 24.0) or 24.0),
        "humidity": float(getattr(env, "humidity", 70.0) or 70.0),
        "rainfall": rainfall,
        "rainfall_24h_mm": rainfall,
        "antecedent_rainfall_7d": antecedent_7d,
        "rainfall_72h_mm": rainfall_72h,
        "slope_angle_deg": env.slope,
        "slope_deg": env.slope,
        "elevation_m": env.elevation,
        "ndvi": env.ndvi,
        "historical_freq": terrain["historical_freq"],
        "friction_angle_deg": terrain["friction_angle_deg"],
        "cohesion_kpa": terrain["cohesion_kpa"],
    }

    # Execute ML inference and geotechnical Factor of Safety
    ml_probability = predict_landslide_probability(features)
    fs = calculate_factor_of_safety(terrain, soil, pore)
    geo_score = max(0.0, min(100.0, 100.0 * (1.55 - fs) / 0.75))

    logger.info(
        "Landslide Risk Pipeline: loc=%s, rain_24h=%.1fmm, soil=%.1f%%, pore=%.2fkPa, slope=%.1f deg -> ML_prob=%.2f%%, FS=%.2f",
        location_name, rainfall, soil, pore, env.slope, ml_probability * 100.0, fs
    )

    rain_stress = min(1.0, rainfall / max(thresholds["rainfall_24h_high_mm"], 1))
    soil_stress = min(1.0, soil / max(thresholds["soil_moisture_high_pct"], 1))
    pore_stress = min(1.0, pore / max(thresholds["pore_pressure_high_kpa"], 1))
    tilt_stress = min(1.0, tilt / max(thresholds["tilt_high_deg"], 0.1))
    criteria_score = 100 * (0.28*rain_stress + 0.27*soil_stress + 0.30*pore_stress + 0.15*tilt_stress)

    final_score_raw = 0.55 * (ml_probability * 100) + 0.25 * geo_score + 0.20 * criteria_score
    score, level = classify_risk(final_score_raw)

    factors = {
        "soil_saturation": _criteria_status(soil, thresholds["soil_moisture_high_pct"], min(99, thresholds["soil_moisture_high_pct"] + 10)),
        "pore_water_pressure": _criteria_status(pore, thresholds["pore_pressure_high_kpa"], thresholds["pore_pressure_high_kpa"] * 1.35),
        "rainfall_24h": _criteria_status(rainfall, thresholds["rainfall_24h_high_mm"], thresholds["rainfall_24h_high_mm"] * 1.5),
        "tilt": "NORMAL",
        "slope_geometry": "HIGH" if env.slope >= 32 else ("MODERATE" if env.slope >= 20 else "NORMAL"),
        "historical_frequency": "HIGH" if terrain["historical_freq"] >= 6 else ("MODERATE" if terrain["historical_freq"] >= 3 else "NORMAL"),
    }
    if tilt > 0:
        factors["tilt"] = _criteria_status(tilt, thresholds["tilt_high_deg"], thresholds["tilt_high_deg"] * 1.5)

    if level == "CRITICAL":
        recommendation = "CRITICAL: initiate emergency response protocol, verify field conditions, and follow official evacuation guidance."
    elif level == "HIGH":
        recommendation = "HIGH: intensify monitoring, verify vulnerable slopes, and prepare early-warning action for exposed communities."
    elif level == "MODERATE":
        recommendation = "MODERATE: continue close monitoring of rainfall, saturation and ground movement; review local advisories."
    else:
        recommendation = "LOW: no elevated software signal detected; continue routine monitoring."

    source = "SOFTWARE_LIVE"
    if sensor_data and any(v is not None for v in sensor_data.model_dump().values()):
        source = "SENSOR_SIMULATION"

    snapshot = SensorSnapshot(
        source=source,
        soil_moisture=round(soil, 2),
        pore_pressure_kpa=round(pore, 3),
        tilt_degrees=round(tilt, 2),
        rainfall_level_mm=round(rainfall, 2),
        connected=False,
    )

    build_notes = [
        "Rainfall, soil saturation, pore-water pressure and slope geometry are evaluated as the primary triggers.",
        "Pore pressure is ESTIMATED from live rainfall + site infiltration parameters via an antecedent-index model.",
        "Rainfall alone does not determine pore pressure; site calibration with a real piezometer is required for measured values.",
        "The ML model is physically-inspired and trained on synthetic data for the SIH prototype; it is not a validated operational warning model.",
        "Tilt is hardware-sensor-only and is NOT fabricated in software mode.",
        "Final score blends ML probability, a simplified Mohr-Coulomb factor-of-safety screen and the trigger-stress score.",
        f"Region resolved: {region_cfg['region_label']}. {region_cfg['calibration']['label']}",
        f"Data quality: {data_quality}. Live rainfall fetch {'OK' if rainfall_fetch_ok else 'UNAVAILABLE'}.",
    ]
    notes = [f"Pipeline note: {n}" for n in notes] + build_notes

    # Dynamic explanation of why the risk is at its current level
    why_reasons = []
    if rainfall >= thresholds["rainfall_24h_high_mm"]:
        why_reasons.append(f"Heavy recent rainfall ({rainfall:.1f} mm/24h exceeds threshold of {thresholds['rainfall_24h_high_mm']} mm)")
    elif rainfall > 15.0:
        why_reasons.append(f"Moderate cumulative precipitation ({rainfall:.1f} mm in 24h)")

    if env.slope >= 34.0:
        why_reasons.append(f"Steep terrain slope ({env.slope:.1f}°), increasing shear gravitational stress")
    elif env.slope >= 25.0:
        why_reasons.append(f"Moderate mountainous slope geometry ({env.slope:.1f}°)")

    if soil >= thresholds["soil_moisture_high_pct"]:
        why_reasons.append(f"Elevated soil saturation ({soil:.1f}% approaching full capacity)")
    elif soil > 45.0:
        why_reasons.append(f"Substantial antecedent soil moisture ({soil:.1f}%)")

    if pore >= thresholds["pore_pressure_high_kpa"]:
        why_reasons.append(f"High pore-water pressure ({pore:.1f} kPa) reducing effective normal stress")

    if terrain["historical_freq"] >= 6:
        why_reasons.append(f"High historical landslide susceptibility corridor (index {terrain['historical_freq']}/10)")

    if fs < 1.0:
        why_reasons.append(f"Mohr-Coulomb Factor of Safety below unity (FS = {fs:.2f} < 1.0, critical instability)")
    elif fs < 1.3:
        why_reasons.append(f"Reduced geotechnical stability margin (Factor of Safety = {fs:.2f})")

    if not why_reasons:
        why_reasons.append("Environmental parameters and slope geometry remain within normal stable thresholds.")

    # Build explicit mathematical and geotechnical calculation breakdown for judges/engineers
    calc_breakdown = {
        "pore_pressure": {
            "formula": "u = γ_w · h_w = γ_w · [z_soil · (S_eff)]",
            "gamma_w_kpa_m": 9.81,
            "soil_depth_m": terrain["soil_depth_m"],
            "porosity": terrain["porosity"],
            "soil_moisture_pct": round(soil, 1),
            "rainfall_24h_mm": round(rainfall, 1),
            "rainfall_72h_mm": round(rainfall_72h, 1),
            "ari_mm": pore_details.get("antecedent_rainfall_index_mm", 0.0),
            "effective_water_head_m": pore_details.get("water_head_m", 0.0),
            "calculated_u_kpa": round(pore, 3),
            "high_threshold_kpa": thresholds["pore_pressure_high_kpa"],
            "interpretation": f"At {soil:.1f}% soil saturation and {rainfall:.1f} mm rain, estimated head is {pore_details.get('water_head_m', 0.0):.3f} m yielding u = {pore:.2f} kPa."
        },
        "factor_of_safety": {
            "formula": "FS = [c' + (σ_n - u) · tan(φ')] / τ_shear",
            "cohesion_c_prime_kpa": terrain["cohesion_kpa"],
            "friction_angle_phi_deg": terrain["friction_angle_deg"],
            "slope_beta_deg": env.slope,
            "total_normal_stress_sigma_n_kpa": round(terrain["unit_weight_kN_m3"] * terrain["soil_depth_m"] * (math.cos(math.radians(env.slope))**2), 2),
            "pore_pressure_u_kpa": round(pore, 3),
            "effective_normal_stress_kpa": round(max(0.0, (terrain["unit_weight_kN_m3"] * terrain["soil_depth_m"] * (math.cos(math.radians(env.slope))**2)) - pore), 2),
            "shear_stress_tau_kpa": round(terrain["unit_weight_kN_m3"] * terrain["soil_depth_m"] * math.sin(math.radians(env.slope)) * math.cos(math.radians(env.slope)), 2),
            "calculated_fs": fs,
            "interpretation": f"FS = {fs:.2f} ({"CRITICAL < 1.0" if fs < 1.0 else ("MARGINAL < 1.3" if fs < 1.3 else "STABLE > 1.3")})"
        },
        "composite_risk_score": {
            "formula": "Risk = 0.55 · (ML_Prob · 100) + 0.25 · Geo_Score + 0.20 · Criteria_Stress",
            "ml_probability_pct": round(ml_probability * 100, 1),
            "ml_contribution": round(0.55 * (ml_probability * 100), 1),
            "geotechnical_score": round(geo_score, 1),
            "geotechnical_contribution": round(0.25 * geo_score, 1),
            "criteria_stress_score": round(criteria_score, 1),
            "criteria_contribution": round(0.20 * criteria_score, 1),
            "total_score_raw": round(final_score_raw, 1),
            "final_score": score,
            "classification": level
        }
    }

    result = RiskResult(
        location=location_name, latitude=lat, longitude=lon,
        risk_score=score, risk_level=level,
        risk_probability=round(score/100, 4),
        ml_probability=round(ml_probability, 4),
        factor_of_safety=fs,
        geotechnical_score=round(geo_score, 2),
        factors=factors,
        recommendation=recommendation,
        timestamp=datetime.now(timezone.utc).isoformat(),
        environmental_data=env,
        thresholds=thresholds,
        geotechnical={
            "factor_of_safety": fs,
            "cohesion_kpa": terrain["cohesion_kpa"],
            "friction_angle_deg": terrain["friction_angle_deg"],
            "soil_depth_m": terrain["soil_depth_m"],
        },
        sensor_snapshot=snapshot,
        calculation_notes=notes,
        region=region_id,
        region_label=region_cfg["region_label"],
        data_quality=data_quality,
        data_status=data_status,
        data_source_label=data_source_label,
        data_freshness=datetime.now(timezone.utc).isoformat(),
        pore_pressure_type=pore_type,
        rainfall_fetch_ok=rainfall_fetch_ok,
        rainfall_details=rainfall_details,
        pore_pressure_details=pore_details,
        why_explanation=why_reasons,
        calculation_breakdown=calc_breakdown,
    )

    try:
        doc = result.model_dump()
        db_manager.risk_assessments.insert_one(doc)
        if score >= 61:
            db_manager.alerts.insert_one({
                "location": location_name, "latitude": lat, "longitude": lon,
                "risk_score": score, "risk_level": level,
                "region": region_id,
                "reasons": [f"{k.replace('_', ' ')} = {v}" for k, v in factors.items() if v in ("HIGH", "CRITICAL")],
                "recommendation": recommendation,
                "timestamp": result.timestamp,
            })
    except Exception as exc:
        logger.exception("Failed to persist risk assessment.")
        raise RuntimeError("Risk calculation succeeded, but result persistence failed.") from exc

    # Automatic SOS for HIGH/CRITICAL (cooldown-protected). Does NOT fire on
    # DATA_UNAVAILABLE because we never auto-declare CRITICAL from missing data.
    # Dispatches immediately to all verified residents registered for this location or state.
    if score >= 61 and data_quality != "DATA_UNAVAILABLE":
        try:
            from .monitor import auto_dispatch
            auto_dispatch(
                location_name, score, level, recommendation,
                region_id=region_id,
                rainfall=rainfall if rainfall_fetch_ok else None,
                rainfall_window=rainfall_details.get("rainfall_window", "24h") if rainfall_details else "24h",
                pore_pressure=pore,
                threshold=thresholds.get("pore_pressure_high_kpa"),
                data_source=data_source_label,
            )
        except Exception as exc:
            logger.warning("Automatic SOS dispatch attempt failed: %s", exc)

    return result
