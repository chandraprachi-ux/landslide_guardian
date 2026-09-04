"""
Estimated pore-pressure module.

AUTHORITATIVE SINGLE SOURCE for computing ESTIMATED pore-water pressure from
rainfall and site parameters. Do NOT duplicate this calculation elsewhere.

SCIENTIFIC BASIS
----------------
Below the groundwater table (saturated):
        u = gamma_w * h_w
where:
    u        = pore-water pressure            [kPa]
    gamma_w  = unit weight of water ≈ 9.81    [kN/m^3]
    h_w      = water-pressure head            [m]

For unsaturated soil the relevant quantity is matric suction:
        s = u_a - u_w
Rainfall infiltration increases water content, reduces suction, raises
saturation, and can build positive pore pressure near the water table, which
reduces effective stress (sigma' = sigma - u) and hence stability.

LIMITATION
----------
Rainfall alone canNOT uniquely determine absolute pore pressure. Actual pore
pressure depends on permeability, hydraulic conductivity, initial conditions,
groundwater depth and site-specific calibration. This module therefore:

    * uses an antecedent-rainfall index (exponentially weighted) to capture
      cumulative wetting and drainage,
    * converts a fraction of that wetting into an estimated water-head rise,
    * and CLEARLY labels the output as ESTIMATED (not measured).

The architecture stays ready to accept MEASURED pore pressure from a real
piezometer/sensor in hardware mode (see `pore_pressure_type`).

UNITS SUMMARY
    rainfall       mm or mm/24h
    soil depth     m
    water gamma    kN/m^3  (== kPa per metre of head)
    pore pressure  kPa
"""

from datetime import datetime, timezone

from .region_config import GAMMA_WATER_KPA

# ---------------------------------------------------------------------------
# Antecedent Rainfall Index (ARI)
# ---------------------------------------------------------------------------

def antecedent_rainfall_index(rainfall_24h_mm: float, rainfall_72h_mm: float,
                              drainage_constant_hours: float = 36.0) -> float:
    """
    Exponentially-weighted measure of recent wetting.

        ARI = sum( rainfall_window_i * exp(-t_i / T_drain) )

    Simplified from 24h and 72h windows:
        ARI ≈ R24 + 0.5 * R72   (approximation the older window is ~ half weight)

    A correct implementation would use the full hourly series and a site
    drainage constant; this is a screening approximation labelled as such.

    Returns an index in mm-equivalent units.
    """
    # Drainage factor in [0,1] - how much the older rain still contributes.
    drain_factor = min(1.0, max(0.15, 48.0 / max(drainage_constant_hours, 6.0)))
    r24 = max(0.0, float(rainfall_24h_mm or 0))
    r72 = max(0.0, float(rainfall_72h_mm or 0))
    return round(r24 + drain_factor * (r72 - r24) * 0.5, 3)


def estimated_water_head_mm(ari_mm: float, porosity: float,
                            max_saturation_rise: float = 0.55,
                            response_ratio: float = 1.0) -> float:
    """
    Estimate the build-up of water head (in mm of equivalent rainfall depth)
    that translates into a pore-pressure change.

        h_water = ARI * infiltration_fraction

    where infiltration_fraction = max_saturation_rise * response_ratio.

    The water head is capped by the site's storage capacity so it cannot
    exceed realistic limits.
    """
    storage_capacity_mm = max(50.0, porosity * 600.0)  # rough moisture-store budget
    frac = max(0.0, min(1.0, max_saturation_rise * response_ratio))
    head = ari_mm * frac
    return round(min(head, storage_capacity_mm), 3)


def estimated_pore_pressure(rainfall_24h_mm: float,
                            rainfall_72h_mm: float,
                            soil_depth_m: float,
                            porosity: float,
                            antecedent_head_mm: float = 0.0,
                            drainage_constant_hours: float = 36.0,
                            max_saturation_rise: float = 0.55) -> dict:
    """
    Estimate pore pressure (kPa) from rainfall + site parameters.

    Returns a dict with the value, its type (always "estimated" here), the
    derivation steps, and units, so callers and the UI can be explicit.
    """
    ari = antecedent_rainfall_index(rainfall_24h_mm, rainfall_72h_mm, drainage_constant_hours)

    # Combine live ARI with any incoming antecedent head (from stored history).
    total_wetting_mm = ari + max(0.0, antecedent_head_mm)

    head_mm = estimated_water_head_mm(total_wetting_mm, porosity, max_saturation_rise)

    # Convert a 1-D water head over the soil profile to pore pressure.
    # h_effective = head_mm scaled by the soil depth available for build-up.
    scale = max(0.15, min(1.0, soil_depth_m / 2.5))
    head_m = (head_mm / 1000.0) * scale

    value_kpa = round(GAMMA_WATER_KPA * head_m, 4)

    return {
        "value_kpa": value_kpa,
        "pore_pressure_type": "estimated",   # NOT measured (no piezometer)
        "antecedent_rainfall_index_mm": ari,
        "wetting_depth_mm": head_mm,
        "water_head_m": round(head_m, 4),
        "unit_weight_kN_m3": GAMMA_WATER_KPA,
        "soil_depth_m": soil_depth_m,
        "porosity": porosity,
        "drainage_constant_hours": drainage_constant_hours,
        "max_saturation_rise": max_saturation_rise,
        "model": "antecedent-index + hydrostatic-head infiltration estimate",
        "label": "ESTIMATED pore pressure (site calibration required). Not a measured piezometer value.",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
