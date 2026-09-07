from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class LocationItem(BaseModel):
    name: str
    state: str
    latitude: float
    longitude: float
    slope: float
    elevation: float
    historical_frequency: int


class SensorInput(BaseModel):
    """Optional future sensor payload. All fields are optional so the SIH demo is 100% software-only."""
    soil_moisture: Optional[float] = Field(default=None, ge=0, le=100)
    pore_pressure_kpa: Optional[float] = Field(default=None, ge=0, le=500)
    tilt_degrees: Optional[float] = Field(default=None, ge=0, le=45)
    rainfall_level_mm: Optional[float] = Field(default=None, ge=0, le=1000)


class PredictRequest(BaseModel):
    location_name: str = Field(min_length=1, max_length=200)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    sensor_data: Optional[SensorInput] = None


class EnvironmentalData(BaseModel):
    rainfall_1h: float = 0.0
    rainfall_3h: float = 0.0
    rainfall_24h: float = 0.0
    rainfall_72h: float = 0.0
    rainfall_intensity: float = 0.0
    soil_moisture: float = 50.0
    humidity: float = 75.0
    temperature: float = 22.0
    wind_speed: float = 10.0
    slope: float = 25.0
    elevation: float = 1000.0
    aspect: float = 180.0
    ndvi: float = 0.4
    distance_to_road: float = 400.0
    pore_pressure_kpa: float = 0.0
    data_source: str = "LIVE_API"


class SensorSnapshot(BaseModel):
    source: str = "SOFTWARE_DEMO"
    soil_moisture: float
    pore_pressure_kpa: float
    tilt_degrees: float
    rainfall_level_mm: float
    connected: bool = False


class RiskResult(BaseModel):
    location: str
    latitude: float
    longitude: float
    risk_score: int
    risk_level: str
    risk_probability: float
    ml_probability: float
    factor_of_safety: Optional[float] = None
    geotechnical_score: float
    factors: Dict[str, str]
    recommendation: str
    timestamp: str
    environmental_data: EnvironmentalData
    thresholds: Dict[str, float]
    geotechnical: Dict[str, float]
    sensor_snapshot: SensorSnapshot
    calculation_notes: List[str] = Field(default_factory=list)

    # New Rainfall -> Pore Pressure -> Risk pipeline metadata.
    region: str = "assam"
    region_label: str = "Assam"
    data_quality: str = "LIVE"          # LIVE | STALE | DATA_UNAVAILABLE
    data_status: str = ""               # NO_RAIN | RAIN | NO_DATA
    data_source_label: str = "OPEN_METEO_LIVE"
    data_freshness: str = ""            # human-readable last-updated
    pore_pressure_type: str = "estimated"
    rainfall_fetch_ok: bool = True
    rainfall_details: Dict = Field(default_factory=dict)
    pore_pressure_details: Dict = Field(default_factory=dict)
    why_explanation: List[str] = Field(default_factory=list)
    calculation_breakdown: Dict = Field(default_factory=dict)


class SensorReading(BaseModel):
    """Future ESP32-compatible payload; not required for the current software demo."""
    device_id: str = Field(min_length=1, max_length=50)
    section_id: str = Field(default="S1", min_length=1, max_length=20)
    soil_moisture: float = Field(ge=0, le=100)
    accel_x: float = 0.0
    accel_y: float = 0.0
    accel_z: float = 9.80665
    gyro_x: float = 0.0
    gyro_y: float = 0.0
    gyro_z: float = 0.0
    tilt_x: Optional[float] = None
    tilt_y: Optional[float] = None
    rainfall_detected: bool = False
    rainfall_value: float = Field(default=0.0, ge=0)
    pore_pressure_kpa: Optional[float] = Field(default=None, ge=0, le=500)
    latitude: float = Field(default=27.3389, ge=-90, le=90)
    longitude: float = Field(default=88.6065, ge=-180, le=180)


class SensorResponse(BaseModel):
    status: str
    device_id: str
    section_id: str
    movement_g: float
    tilt_degrees: float
    soil_moisture: float
    rainfall_detected: bool
    pore_pressure_kpa: Optional[float] = None
    storage_mode: str


class CitizenRegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: str = Field(min_length=5, max_length=200)
    location: str = Field(min_length=1, max_length=200)


class UserRegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: str = Field(min_length=5, max_length=200)
    region: str = Field(min_length=1, max_length=100)


class SendOtpRequest(BaseModel):
    email: str = Field(min_length=5, max_length=200)


class VerifyOtpRequest(BaseModel):
    email: str = Field(min_length=5, max_length=200)
    code: str = Field(min_length=4, max_length=12)


class SOSBroadcastRequest(BaseModel):
    location: str = Field(min_length=1, max_length=200)
    custom_message: Optional[str] = Field(default=None, max_length=1000)


class AdminLoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=200)
