from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from ..models.schemas import PredictRequest
from ..services.pore_pressure import estimated_pore_pressure
from ..services.rainfall_service import (
    RainfallUnavailable, append_rainfall_record, get_live_rainfall,
    get_recent_rainfall,
)
from ..services.region_config import get_all_regions, get_region_config, get_region_for_location
from ..services.risk_service import calculate_risk_assessment

router = APIRouter()


def _resolve(location_name: str = "", latitude: float = None, longitude: float = None):
    return location_name or "Gangtok, Sikkim", float(latitude or 27.3389), float(longitude or 88.6065)


@router.get("/regions")
async def list_regions():
    """All monitored regions with their anchors."""
    return {"count": len(get_all_regions()), "regions": get_all_regions()}


@router.get("/regions/{region}")
async def region_detail(region: str):
    cfg = get_region_config(region)
    if cfg["region"] != region.lower():
        raise HTTPException(status_code=404, detail="Unknown region.")
    return cfg


@router.get("/weather/live")
async def weather_live(location: str = "Gangtok, Sikkim",
                       latitude: float = Query(default=27.3389),
                       longitude: float = Query(default=88.6065)):
    name, lat, lon = _resolve(location, latitude, longitude)
    from ..services.weather_service import fetch_environmental_data
    env = await fetch_environmental_data(lat, lon)
    return {
        "location": name,
        "latitude": lat, "longitude": lon,
        "temperature_c": env.temperature,
        "humidity_pct": env.humidity,
        "wind_speed_kmh": env.wind_speed,
        "soil_moisture_pct": round(env.soil_moisture, 2),
        "rainfall_1h_mm": env.rainfall_1h,
        "rainfall_24h_mm": env.rainfall_24h,
        "rainfall_72h_mm": env.rainfall_72h,
        "data_source": env.data_source,
        "data_quality": "LIVE" if env.data_source != "WEATHER_FALLBACK" else "DATA_UNAVAILABLE",
    }


@router.get("/rainfall/live")
async def rainfall_live(location: str = "Gangtok, Sikkim",
                        latitude: float = Query(default=27.3389),
                        longitude: float = Query(default=88.6065)):
    name, lat, lon = _resolve(location, latitude, longitude)
    try:
        live = await get_live_rainfall(name, lat, lon)
        # Append the observation (dedup-protected) so Live Now stores it.
        appended = append_rainfall_record(live)
        return {"success": True, "observation": appended}
    except RainfallUnavailable as exc:
        return {
            "success": False,
            "location": name,
            "latitude": lat, "longitude": lon,
            "data_quality": "DATA_UNAVAILABLE",
            "data_status": "NO_DATA",
            "reason": str(exc),
            "message": "LIVE DATA UNAVAILABLE — weather provider could not be reached. No synthetic data is substituted.",
        }


@router.get("/rainfall/history")
async def rainfall_history(location: str = "Gangtok, Sikkim",
                           latitude: float = Query(default=27.3389),
                           longitude: float = Query(default=88.6065),
                           limit: int = Query(default=10, le=50)):
    name, lat, lon = _resolve(location, latitude, longitude)
    return get_recent_rainfall(name, lat, lon, limit)


@router.post("/pore-pressure/calculate")
async def pore_pressure_calculate(location: str = "Gangtok, Sikkim",
                                  rainfall_24h_mm: float = 0.0,
                                  rainfall_72h_mm: float = 0.0,
                                  latitude: float = Query(default=27.3389),
                                  longitude: float = Query(default=88.6065)):
    region = get_region_for_location(location, latitude, longitude)
    cfg = get_region_config(region)
    site = cfg["site"]
    result = estimated_pore_pressure(
        rainfall_24h_mm=rainfall_24h_mm,
        rainfall_72h_mm=rainfall_72h_mm,
        soil_depth_m=site["soil_depth_m"],
        porosity=site["porosity"],
        drainage_constant_hours=site["infiltration"]["drainage_constant_hours"],
        max_saturation_rise=site["infiltration"]["max_saturation_rise"],
    )
    return {
        "region": cfg["region"],
        "region_label": cfg["region_label"],
        "rainfall_24h_mm": rainfall_24h_mm,
        "rainfall_72h_mm": rainfall_72h_mm,
        "threshold_high_kpa": cfg["thresholds"]["pore_pressure_high_kpa"],
        "threshold_critical_kpa": cfg["thresholds"]["pore_pressure_critical_kpa"],
        **result,
    }


@router.post("/prediction/live")
async def prediction_live(req: PredictRequest):
    """Full Live Now prediction: real rainfall -> estimated pore pressure ->
    region threshold -> risk -> existing ML assessment.
    """
    result = await calculate_risk_assessment(
        req.location_name, req.latitude, req.longitude, req.sensor_data
    )
    return {
        "location": result.location,
        "region": result.region,
        "region_label": result.region_label,
        "latitude": result.latitude,
        "longitude": result.longitude,
        "weather": result.rainfall_details.get("weather_condition") if result.rainfall_details else None,
        "rainfall": result.rainfall_details.get("rainfall_24h_mm") if result.rainfall_details else result.environmental_data.rainfall_24h,
        "rainfall_window": "24h",
        "timestamp": result.timestamp,
        "pore_pressure": result.pore_pressure_details.get("value_kpa") if result.pore_pressure_details else None,
        "pore_pressure_type": result.pore_pressure_type,
        "threshold": result.thresholds.get("pore_pressure_high_kpa"),
        "risk_level": result.risk_level,
        "risk_score": result.risk_score,
        "landslide_assessment": result.recommendation,
        "ml_probability": result.ml_probability,
        "factor_of_safety": result.geotechnical.get("factor_of_safety"),
        "data_source": result.data_source_label,
        "data_quality": result.data_quality,
        "data_status": result.data_status,
        "data_freshness": result.data_freshness,
        "tilt": "Hardware Sensor Only",
        "why_explanation": getattr(result, "why_explanation", []),
        "full_result": result.model_dump(),
    }


@router.get("/location/detail")
async def location_detail(name: str = Query("Rimbi"),
                          lat: Optional[float] = Query(default=None),
                          lon: Optional[float] = Query(default=None)):
    """
    Detailed weather-card query for any location/sub-location in the NER.
    Coordinates take precedence if passed, otherwise looks up named sub-location.
    Fetches real coordinate weather, calculates terrain slope, estimated pore pressure,
    and runs the Random Forest ML risk engine.
    """
    from ..services.geo_hierarchy import get_location_by_name, get_location
    if lat is None or lon is None:
        sub = get_location_by_name(name)
        if sub:
            lat = sub["lat"]
            lon = sub["lon"]
            name = f"{sub['name']}, {sub['state']}"
        else:
            lat, lon = 27.2025, 88.2114  # Default to Rimbi if unknown
            name = name or "Rimbi, Sikkim"

    result = await calculate_risk_assessment(name, float(lat), float(lon))
    return {
        "location": result.location,
        "region": result.region,
        "region_label": result.region_label,
        "latitude": result.latitude,
        "longitude": result.longitude,
        "risk_score": result.risk_score,
        "risk_level": result.risk_level,
        "risk_probability": result.risk_probability,
        "ml_probability": result.ml_probability,
        "geotechnical_score": result.geotechnical_score,
        "rainfall_24h_mm": result.rainfall_details.get("rainfall_24h_mm", result.environmental_data.rainfall_24h),
        "rainfall_72h_mm": result.environmental_data.rainfall_72h,
        "temperature_c": result.environmental_data.temperature,
        "humidity_pct": result.environmental_data.humidity,
        "wind_speed_kmh": result.environmental_data.wind_speed,
        "soil_moisture_pct": round(result.environmental_data.soil_moisture, 1),
        "pore_pressure_kpa": result.pore_pressure_details.get("value_kpa", 0.0),
        "pore_pressure_type": result.pore_pressure_type,
        "elevation_m": result.environmental_data.elevation,
        "slope_deg": result.environmental_data.slope,
        "factor_of_safety": result.geotechnical.get("factor_of_safety"),
        "factors": result.factors,
        "thresholds": result.thresholds,
        "why_explanation": getattr(result, "why_explanation", []),
        "recommendation": result.recommendation,
        "data_quality": result.data_quality,
        "data_status": result.data_status,
        "data_source": result.data_source_label,
        "timestamp": result.timestamp,
        "sensor_snapshot": result.sensor_snapshot.model_dump(),
        "calculation_breakdown": result.calculation_breakdown,
    }


@router.get("/map/layers")
async def get_map_layers(layer_type: str = Query(default="all")):
    """
    Returns active regional layer features (sub-locations, hotspots, historical points, sensor nodes)
    for weather-style interactive visualization.
    """
    from ..services.geo_hierarchy import NER_SUBLOCATIONS, NER_REGIONS
    from ..services.monitor import get_active_hotspots

    # Historical landslide reference points in the NER
    historical_points = [
        {"name": "South Lhonak Lake GLOF Valley", "region": "Sikkim", "lat": 27.9100, "lon": 88.2000, "year": 2023, "type": "GLOF & Valley Wall Slump", "impact": "Severe downstream flash flooding and highway severing."},
        {"name": "Tupul Railway Debris Avalanche", "region": "Manipur", "lat": 24.7083, "lon": 93.6333, "year": 2022, "type": "Debris Avalanche", "impact": "Massive slope failure burying railway construction yard."},
        {"name": "Dima Hasao Hill Rail Slip", "region": "Assam", "lat": 25.1764, "lon": 93.0200, "year": 2022, "type": "Rotational Rock/Soil Slide", "impact": "Track formation collapse near New Haflong station."},
        {"name": "Durtlang Ridge Collapse", "region": "Mizoram", "lat": 23.7833, "lon": 92.7333, "year": 2019, "type": "Fault-controlled Rockslide", "impact": "Major cliff displacement threatening residential hospital."},
        {"name": "Mawlai Escarpment Road Slide", "region": "Meghalaya", "lat": 25.6025, "lon": 91.8744, "year": 2021, "type": "Road Cut Mudslide", "impact": "GS Road blocked by sudden colluvial flow."},
        {"name": "Banderdewa Bypass Slump", "region": "Arunachal Pradesh", "lat": 27.1350, "lon": 93.8167, "year": 2020, "type": "Siwalik Soil Slip", "impact": "Arunachal border highway subsidence."},
        {"name": "Dzükou Valley Footpath Slide", "region": "Nagaland", "lat": 25.5539, "lon": 94.0628, "year": 2021, "type": "Alpine Scree Slide", "impact": "Trek route breach following continuous precipitation."},
        {"name": "Baramura Pass Inundation Slide", "region": "Tripura", "lat": 23.8750, "lon": 91.5650, "year": 2018, "type": "Cut-slope Debris Flow", "impact": "NH-8 disrupted during monsoon depression."},
    ]

    # Sensor deployment nodes
    sensor_nodes = [
        {"node_id": "SN-SIK-001", "location": "Rimbi Valley Station", "region": "Sikkim", "lat": 27.2025, "lon": 88.2114, "status": "ONLINE", "type": "Piezometer + Tiltmeter", "depth_m": 2.2},
        {"node_id": "SN-SIK-002", "location": "Gangtok NH-10 Slope", "region": "Sikkim", "lat": 27.3389, "lon": 88.6065, "status": "ONLINE", "type": "Inclinometer Array", "depth_m": 3.0},
        {"node_id": "SN-MEG-001", "location": "Mawlai Escarpment", "region": "Meghalaya", "lat": 25.6025, "lon": 91.8744, "status": "ONLINE", "type": "Pore Pressure Transducer", "depth_m": 2.0},
        {"node_id": "SN-MIZ-001", "location": "Durtlang Fault Face", "region": "Mizoram", "lat": 23.7833, "lon": 92.7333, "status": "ONLINE", "type": "Crack Extensometer", "depth_m": 1.5},
        {"node_id": "SN-MAN-001", "location": "Tupul Railway Bridge Pier", "region": "Manipur", "lat": 24.7083, "lon": 93.6333, "status": "ONLINE", "type": "Wireless Tilt & Rain Gauge", "depth_m": 2.5},
        {"node_id": "SN-ASM-001", "location": "Haflong Hill Cut", "region": "Assam", "lat": 25.1764, "lon": 93.0200, "status": "ONLINE", "type": "Piezometer Node", "depth_m": 2.0},
    ]

    return {
        "sublocations": NER_SUBLOCATIONS,
        "regions": list(NER_REGIONS.values()),
        "hotspots": get_active_hotspots(),
        "historical_events": historical_points,
        "sensor_nodes": sensor_nodes,
    }
