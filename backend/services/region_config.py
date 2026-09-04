"""
Regional / site configuration for the Landslide Guardian rainfall-to-risk pipeline.

This module is the SINGLE authoritative source for location-specific:

    - region grouping (Sikkim, Assam, Meghalaya, Mizoram, Nagaland,
      Arunachal Pradesh, Manipur, Tripura)
    - rainfall / infiltration parameters
    - expected / estimated pore-pressure parameters
    - risk threshold boundaries
    - calibration parameters

IMPORTANT (scientific honesty):
- No threshold here is claimed to be officially validated. All values are
  prototype / research-fit calibration constants pulled from the city-level
  geotechnical profiles already present in the project (see
  `terrain_service.NER_PROFILES`). They must be calibrated against real
  site investigation data and measured piezometers before operational use.
- Rainfall alone cannot determine absolute pore pressure. The estimated
  pore pressure produced by the pore-pressure module is an *estimate*,
  clearly labelled as such, and must be replaced by real sensor measurements
  when piezometers become available.
"""

from .terrain_service import NER_PROFILES, NER_COORDS

# Water unit weight (kN/m^3) at ~standard conditions.
GAMMA_WATER_KPA = 9.81       # kN/m^3 == kPa per metre of water head

# Default infiltration model parameters (see pore_pressure.py for meaning).
# These are physically-plausible starting values; calibrate per site.
DEFAULT_INFILTRATION = {
    "max_saturation_rise": 0.55,   # fraction of max water-content capacity
    "response_time_hours": 6.0,    # soil-water response lag to rainfall (hr)
    "drainage_constant_hours": 36.0,  # exponential drainage time constant (hr)
}

# Region -> the names/cities that belong to it. Keys are canonical region ids.
# Location matching is case-insensitive substring against city/state names.
REGION_MEMBERS = {
    "sikkim":   ["gangtok"],
    "assam":    ["guwahati"],
    "meghalaya": ["shillong"],
    "mizoram":  ["aizawl"],
    "nagaland": ["kohima"],
    "arunachal_pradesh": ["itanagar"],
    "manipur":  ["imphal"],
    "tripura":  ["agartala"],
}

# Display labels for regions.
REGION_LABELS = {
    "sikkim": "Sikkim",
    "assam": "Assam",
    "meghalaya": "Meghalaya",
    "mizoram": "Mizoram",
    "nagaland": "Nagaland",
    "arunachal_pradesh": "Arunachal Pradesh",
    "manipur": "Manipur",
    "tripura": "Tripura",
}

# Preferred representative city + coordinates for each region (used as the
# weather/rainfall anchor point for that region's monitor slot).
REGION_ANCHOR = {
    "sikkim":   ("Gangtok, Sikkim", 27.3389, 88.6065),
    "assam":    ("Guwahati, Assam", 26.1445, 91.7362),
    "meghalaya": ("Shillong, Meghalaya", 25.5788, 91.8933),
    "mizoram":  ("Aizawl, Mizoram", 23.7271, 92.7176),
    "nagaland": ("Kohima, Nagaland", 25.6740, 94.1086),
    "arunachal_pradesh": ("Itanagar, Arunachal Pradesh", 27.0844, 93.6053),
    "manipur":  ("Imphal, Manipur", 24.8170, 93.9368),
    "tripura":  ("Agartala, Tripura", 23.8315, 91.2868),
}


def _city_profile(city_key: str) -> dict:
    """Return the terrain profile for a city key, or a sensible default."""
    return NER_PROFILES.get(city_key, {
        "state": "NER", "slope": 25.0, "elevation": 1100.0, "historical": 4,
        "aspect": 180.0, "ndvi": 0.40, "road": 400.0, "soil_depth": 2.0,
        "cohesion": 20.0, "phi": 29.0, "porosity": 0.57, "unit_weight": 18.5,
    })


def _porosity_moisture_high(porosity: float) -> float:
    # High-saturation warning ~ just below full saturation, bounded.
    return round(min(95.0, max(70.0, porosity * 100 - 3.0)), 1)


def _pore_high_from_soil_depth(depth_m: float) -> float:
    # Estimated pore-pressure "high" warning: hydrostatic head fraction of
    # soil depth. This is a screening reference, not a site-calibrated value.
    return round(GAMMA_WATER_KPA * depth_m * 0.45, 1)


def get_region_for_location(location_name: str = "", lat: float = None, lon: float = None) -> str:
    """
    Resolve a location (name and/or coordinates) to a region id.

    Prefers an explicit name match; falls back to nearest coordinate anchor.
    """
    from .geo_hierarchy import get_location_by_name, get_location
    sub = get_location_by_name(location_name)
    if sub and sub.get("region_id"):
        return sub["region_id"]

    name = (location_name or "").lower()
    for region, city_keys in REGION_MEMBERS.items():
        label = REGION_LABELS.get(region, region).lower()
        if label in name or region.replace("_", " ") in name:
            return region
        for ck in city_keys:
            if ck in name:
                return region

    if lat is not None and lon is not None:
        sub_c = get_location(lat, lon, max_dist_km=40.0)
        if sub_c and sub_c.get("region_id"):
            return sub_c["region_id"]

        best = None
        best_dist = float("inf")
        for region, (_name, rlat, rlon) in REGION_ANCHOR.items():
            dist = abs(lat - rlat) + abs(lon - rlon)
            if dist < best_dist:
                best_dist = dist
                best = region
        if best:
            return best
    return "assam"


def get_region_config(region_id: str) -> dict:
    """
    Return the full configuration for a region: site params, infiltration
    params, thresholds and metadata.
    """
    region_id = (region_id or "assam").lower().strip()
    city_keys = REGION_MEMBERS.get(region_id)
    if not city_keys:
        # Unknown region -> nearest fallback config.
        region_id = "assam"
        city_keys = REGION_MEMBERS[region_id]

    label = REGION_LABELS.get(region_id, region_id.title())
    anchor_label, anchor_lat, anchor_lon = REGION_ANCHOR[region_id]
    local = _city_profile(city_keys[0])
    slope = local["slope"]
    porosity = local["porosity"]
    soil_depth = local["soil_depth"]

    return {
        "region": region_id,
        "region_label": label,
        "anchor": {"name": anchor_label, "lat": anchor_lat, "lon": anchor_lon},
        "site": {
            "slope_deg": slope,
            "elevation_m": local["elevation"],
            "historical_freq": local["historical"],
            "soil_depth_m": soil_depth,
            "porosity": porosity,
            "cohesion_kpa": local["cohesion"],
            "friction_angle_deg": local["phi"],
            "ndvi": local["ndvi"],
            "infiltration": {
                "max_saturation_rise": DEFAULT_INFILTRATION["max_saturation_rise"],
                "response_time_hours": DEFAULT_INFILTRATION["response_time_hours"],
                "drainage_constant_hours": DEFAULT_INFILTRATION["drainage_constant_hours"],
            },
        },
        "thresholds": {
            # Rainfall high/critical for this region (mm/24h). Screening refs.
            "rainfall_24h_high_mm": round(max(60.0, 135.0 - slope * 1.25), 1),
            "rainfall_24h_critical_mm": round(max(90.0, 200.0 - slope * 1.5), 1),
            # Soil saturation threshold.
            "soil_moisture_high_pct": _porosity_moisture_high(porosity),
            # Pore-pressure (estimated) threshold (kPa). Screening refs.
            "pore_pressure_high_kpa": _pore_high_from_soil_depth(soil_depth),
            "pore_pressure_critical_kpa": round(_pore_high_from_soil_depth(soil_depth) * 1.35, 1),
            # Risk-level boundaries (preserve project labels).
            "risk_low_max": 30,
            "risk_moderate_max": 60,
            "risk_high_max": 80,
        },
        "calibration": {
            "calibrated": False,
            "label": "RESEARCH/CALIBRATION — site-specific calibration required; not officially validated.",
        },
    }


def get_all_regions() -> list:
    """Return a list of region config summaries (for admin/UI)."""
    out = []
    for rid in REGION_LABELS:
        cfg = get_region_config(rid)
        out.append({
            "region": cfg["region"],
            "region_label": cfg["region_label"],
            "anchor": cfg["anchor"]["name"],
            "lat": cfg["anchor"]["lat"],
            "lon": cfg["anchor"]["lon"],
        })
    return out
