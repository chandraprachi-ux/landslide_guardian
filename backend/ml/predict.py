import os
import pickle
import numpy as np
import pandas as pd

MODEL_PATH = os.path.join(os.path.dirname(__file__), "model.pkl")

# Default feature names in trained order
feature_names = [
    "soil_moisture",
    "water_pressure",
    "acceleration",
    "tilt_angle",
    "temperature",
    "humidity",
    "rainfall",
    "antecedent_rainfall_7d",
    "slope_angle_deg"
]

model = None
scaler = None

if os.path.exists(MODEL_PATH):
    try:
        with open(MODEL_PATH, "rb") as f:
            artifact = pickle.load(f)
            if isinstance(artifact, dict) and "model" in artifact:
                model = artifact["model"]
                scaler = artifact.get("scaler")
                feature_names = artifact.get("feature_names", feature_names)
            else:
                model = artifact
    except Exception as e:
        print(f"Warning: Could not load model.pkl: {e}")

# Key mapping aliases for flexibility across API and sensor inputs
_KEY_MAP = {
    "soil_moisture": ["soil_moisture", "soil_moisture_pct", "soil"],
    "water_pressure": ["water_pressure", "pore_pressure", "pore_pressure_kpa", "pwp"],
    "acceleration": ["acceleration", "accel"],
    "tilt_angle": ["tilt_angle", "tilt_degrees", "tilt_deg", "tilt"],
    "temperature": ["temperature", "temp"],
    "humidity": ["humidity"],
    "rainfall": ["rainfall", "rainfall_24h_mm", "rainfall_24h"],
    "antecedent_rainfall_7d": ["antecedent_rainfall_7d", "rainfall_72h_mm", "rainfall_72h", "antecedent"],
    "slope_angle_deg": ["slope_angle_deg", "slope_deg", "slope"]
}

_DEFAULTS = {
    "soil_moisture": 30.0,
    "water_pressure": 1.0,
    "acceleration": 9.81,
    "tilt_angle": 0.05,
    "temperature": 24.0,
    "humidity": 70.0,
    "rainfall": 0.0,
    "antecedent_rainfall_7d": 5.0,
    "slope_angle_deg": 35.0
}

def _resolve_feature(data: dict, canonical_name: str) -> float:
    for alias in _KEY_MAP.get(canonical_name, [canonical_name]):
        if alias in data and data[alias] is not None:
            try:
                return float(data[alias])
            except (ValueError, TypeError):
                pass
    return _DEFAULTS.get(canonical_name, 0.0)

def predict_landslide_probability(*args, **kwargs) -> float:
    """
    Computes landslide probability (0.0 to 1.0).
    Accepts positional values, keyword arguments, or a single dictionary.
    Passes a pandas DataFrame with exact fitted feature names to permanently
    eliminate Scikit-Learn 'UserWarning: X does not have valid feature names'.
    """
    data = {}

    if len(args) == 1 and isinstance(args[0], dict):
        data = dict(args[0])
    elif len(args) > 0:
        for idx, val in enumerate(args):
            if idx < len(feature_names):
                data[feature_names[idx]] = val

    data.update(kwargs)

    # If model is not loaded, fallback to geotechnical risk threshold
    if model is None:
        sm = _resolve_feature(data, "soil_moisture")
        rf = _resolve_feature(data, "rainfall")
        wp = _resolve_feature(data, "water_pressure")
        return 0.85 if (sm > 80.0 or rf > 100.0 or wp > 35.0) else 0.15

    # Extract ordered features mapped to fitted columns
    row = {col: _resolve_feature(data, col) for col in feature_names}
    df_features = pd.DataFrame([row], columns=feature_names)

    if scaler is not None:
        scaled_array = scaler.transform(df_features)
        df_scaled = pd.DataFrame(scaled_array, columns=feature_names)
    else:
        df_scaled = df_features

    if hasattr(model, "predict_proba"):
        prob = float(model.predict_proba(df_scaled)[0][1])
    else:
        prob = float(model.predict(df_scaled)[0])

    return round(prob, 4)

def predict_landslide_risk(sensor_data: dict) -> dict:
    """
    Returns risk level breakdown and triggered flag.
    """
    prob = predict_landslide_probability(sensor_data)
    is_triggered = bool(prob >= 0.50)

    if prob >= 0.75:
        level = "CRITICAL"
    elif prob >= 0.50:
        level = "HIGH"
    elif prob >= 0.25:
        level = "MEDIUM"
    else:
        level = "LOW"

    return {
        "landslide_triggered": is_triggered,
        "probability": prob,
        "risk_level": level
    }