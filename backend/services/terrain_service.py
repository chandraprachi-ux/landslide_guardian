import math
from typing import Tuple

# NER city-level prototype profiles. These are engineering assumptions for a
# software demonstration, not site investigation data.
# soil_depth_m, cohesion_kpa, friction_angle_deg, porosity, saturated_unit_weight_kN_m3
NER_PROFILES = {
    "gangtok":   {"state": "Sikkim", "slope": 36.0, "elevation": 1650.0, "historical": 8, "aspect": 210.0, "ndvi": 0.35, "road": 120.0, "soil_depth": 2.0, "cohesion": 18.0, "phi": 28.0, "porosity": 0.55, "unit_weight": 19.0},
    "shillong":  {"state": "Meghalaya", "slope": 28.0, "elevation": 1525.0, "historical": 5, "aspect": 180.0, "ndvi": 0.45, "road": 300.0, "soil_depth": 1.8, "cohesion": 22.0, "phi": 30.0, "porosity": 0.58, "unit_weight": 18.5},
    "aizawl":    {"state": "Mizoram", "slope": 42.0, "elevation": 1132.0, "historical": 9, "aspect": 250.0, "ndvi": 0.30, "road": 90.0, "soil_depth": 1.6, "cohesion": 15.0, "phi": 27.0, "porosity": 0.60, "unit_weight": 18.5},
    "kohima":    {"state": "Nagaland", "slope": 34.0, "elevation": 1444.0, "historical": 6, "aspect": 200.0, "ndvi": 0.40, "road": 150.0, "soil_depth": 1.9, "cohesion": 17.0, "phi": 28.0, "porosity": 0.57, "unit_weight": 18.8},
    "itanagar":  {"state": "Arunachal Pradesh", "slope": 30.0, "elevation": 320.0,  "historical": 4, "aspect": 160.0, "ndvi": 0.55, "road": 400.0, "soil_depth": 2.2, "cohesion": 20.0, "phi": 29.0, "porosity": 0.62, "unit_weight": 18.2},
    "guwahati":  {"state": "Assam", "slope": 12.0, "elevation": 55.0,   "historical": 2, "aspect": 90.0,  "ndvi": 0.50, "road": 600.0, "soil_depth": 2.0, "cohesion": 28.0, "phi": 32.0, "porosity": 0.52, "unit_weight": 17.8},
    "imphal":    {"state": "Manipur", "slope": 22.0, "elevation": 786.0,  "historical": 3, "aspect": 140.0, "ndvi": 0.48, "road": 350.0, "soil_depth": 2.0, "cohesion": 24.0, "phi": 31.0, "porosity": 0.56, "unit_weight": 18.0},
    "agartala":  {"state": "Tripura", "slope": 8.0,  "elevation": 15.0,   "historical": 1, "aspect": 70.0,  "ndvi": 0.52, "road": 700.0, "soil_depth": 2.0, "cohesion": 30.0, "phi": 33.0, "porosity": 0.50, "unit_weight": 17.5},
}

DEFAULT_PROFILE = {"state": "NER", "slope": 25.0, "elevation": 1100.0, "historical": 4, "aspect": 180.0, "ndvi": 0.40, "road": 400.0, "soil_depth": 2.0, "cohesion": 20.0, "phi": 29.0, "porosity": 0.57, "unit_weight": 18.5}

NER_COORDS = {
    "gangtok": (27.3389, 88.6065), "shillong": (25.5788, 91.8933),
    "aizawl": (23.7271, 92.7176), "kohima": (25.6740, 94.1086),
    "itanagar": (27.0844, 93.6053), "guwahati": (26.1445, 91.7362),
    "imphal": (24.8170, 93.9368), "agartala": (23.8315, 91.2868),
}


def _distance_km(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2-lat1)
    dl = math.radians(lon2-lon1)
    a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 6371.0 * 2 * math.atan2(math.sqrt(a), math.sqrt(max(1-a, 1e-12)))


def get_profile(location_name: str, lat: float, lon: float) -> dict:
    from .geo_hierarchy import get_location_by_name, get_location

    # 1. Check if name matches a known sub-location (e.g., Rimbi, Singlitam, Mawlai, Tupul)
    sub = get_location_by_name(location_name)
    if sub:
        return {
            "state": sub["state"],
            "slope": sub["slope"],
            "elevation": sub["elevation"],
            "historical": sub["historical_freq"],
            "aspect": sub["aspect"],
            "ndvi": 0.40,
            "road": 200.0,
            "soil_depth": sub["soil_depth"],
            "cohesion": sub["cohesion"],
            "phi": sub["phi"],
            "porosity": sub["porosity"],
            "unit_weight": sub["unit_weight"],
            "profile_key": sub["id"]
        }

    # 2. Check if coordinates are close to a known sub-location or need interpolation
    if lat is not None and lon is not None:
        sub_coord = get_location(lat, lon, max_dist_km=15.0)
        if sub_coord and sub_coord.get("match_type") == "named_sublocation":
            return {
                "state": sub_coord["state"],
                "slope": sub_coord["slope"],
                "elevation": sub_coord["elevation"],
                "historical": sub_coord["historical_freq"],
                "aspect": sub_coord["aspect"],
                "ndvi": 0.40,
                "road": 200.0,
                "soil_depth": sub_coord["soil_depth"],
                "cohesion": sub_coord["cohesion"],
                "phi": sub_coord["phi"],
                "porosity": sub_coord["porosity"],
                "unit_weight": sub_coord["unit_weight"],
                "profile_key": sub_coord["id"]
            }

    name = (location_name or "").lower()
    for key, profile in NER_PROFILES.items():
        if key in name:
            out = dict(profile)
            out["profile_key"] = key
            return out

    # Coordinate-based selection makes thresholds location-aware even when
    # the user enters a custom name.
    if lat is not None and lon is not None:
        nearest = min(NER_COORDS, key=lambda k: _distance_km(lat, lon, *NER_COORDS[k]))
        out = dict(NER_PROFILES[nearest])
        out["profile_key"] = f"nearest:{nearest}"
        return out

    return dict(DEFAULT_PROFILE)


def get_terrain_info(location_name: str, lat: float, lon: float) -> Tuple[float, float, int]:
    p = get_profile(location_name, lat, lon)
    return p["slope"], p["elevation"], p["historical"]


def get_full_terrain_info(location_name: str, lat: float, lon: float) -> dict:
    p = get_profile(location_name, lat, lon)
    return {
        "slope_deg": p["slope"],
        "elevation_m": p["elevation"],
        "historical_freq": p["historical"],
        "aspect_deg": p["aspect"],
        "ndvi": p["ndvi"],
        "distance_to_road_m": p["road"],
        "soil_depth_m": p["soil_depth"],
        "cohesion_kpa": p["cohesion"],
        "friction_angle_deg": p["phi"],
        "porosity": p["porosity"],
        "unit_weight_kN_m3": p["unit_weight"],
        "profile_key": p["profile_key"],
    }


def estimate_pore_pressure(soil_moisture_pct: float, profile: dict) -> float:
    """
    Screening estimate only:
    u = gamma_w * h_w, where h_w is an estimated water head driven by
    saturation above a location-specific baseline. Real pore pressure requires
    a piezometer/pressure sensor and site-specific groundwater geometry.
    """
    saturation = max(0.0, min(1.0, soil_moisture_pct / 100.0))
    baseline = max(0.25, min(0.60, profile["porosity"] * 0.72))
    water_head = profile["soil_depth_m"] * max(0.0, saturation - baseline) / max(1.0 - baseline, 0.1)
    return round(9.81 * water_head, 3)


def calculate_factor_of_safety(profile: dict, soil_moisture_pct: float, pore_pressure_kpa: float) -> float:
    """
    Simplified infinite-slope Mohr-Coulomb screening model.
    FS = [c' + (sigma_n - u) tan(phi')] / tau
    """
    beta = math.radians(max(2.0, min(profile["slope_deg"], 65.0)))
    z = profile["soil_depth_m"]
    gamma = profile["unit_weight_kN_m3"]
    sigma_n = gamma * z * math.cos(beta) ** 2
    shear = gamma * z * math.sin(beta) * math.cos(beta)
    effective_normal = max(0.0, sigma_n - max(0.0, pore_pressure_kpa))
    fs = (profile["cohesion_kpa"] + effective_normal * math.tan(math.radians(profile["friction_angle_deg"]))) / max(shear, 0.1)
    return round(max(0.05, min(fs, 5.0)), 3)


def build_thresholds(profile: dict) -> dict:
    slope = profile["slope_deg"]
    return {
        "soil_moisture_high_pct": round(min(92.0, max(68.0, profile["porosity"] * 100 - 2.0)), 1),
        "pore_pressure_high_kpa": round(9.81 * profile["soil_depth_m"] * 0.45, 1),
        "tilt_high_deg": round(max(4.0, min(9.0, 12.0 - slope / 8.0)), 1),
        "rainfall_24h_high_mm": round(max(60.0, 135.0 - slope * 1.25), 1),
        "rainfall_72h_high_mm": round(max(120.0, 260.0 - slope * 2.0), 1),
    }