import math
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from ..database.mongodb import db_manager, clean_document
from ..models.schemas import SensorReading, SensorResponse

router = APIRouter()


def movement_g(ax: float, ay: float, az: float) -> float:
    return math.sqrt(ax*ax + ay*ay + az*az) / 9.80665


def tilt_degrees(ax: float, ay: float, az: float) -> float:
    horizontal = math.sqrt(ax*ax + ay*ay)
    return math.degrees(math.atan2(horizontal, max(abs(az), 0.001)))


@router.post("/sensors/data", response_model=SensorResponse)
async def receive_sensor_data(data: SensorReading):
    timestamp = datetime.now(timezone.utc).isoformat()
    mg = movement_g(data.accel_x, data.accel_y, data.accel_z)
    tilt = tilt_degrees(data.accel_x, data.accel_y, data.accel_z)
    if data.tilt_x is not None and data.tilt_y is not None:
        tilt = math.sqrt(data.tilt_x**2 + data.tilt_y**2)

    document = data.model_dump()
    document.update({"movement_g": mg, "tilt_degrees": tilt, "timestamp": timestamp})

    try:
        db_manager.sensor_readings.insert_one(document)
        db_manager.sensor_latest.update_one(
            {"device_id": data.device_id, "section_id": data.section_id},
            {"$set": document}, upsert=True
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Could not store future sensor reading.") from exc

    return SensorResponse(
        status="accepted", device_id=data.device_id, section_id=data.section_id,
        movement_g=round(mg, 4), tilt_degrees=round(tilt, 2),
        soil_moisture=data.soil_moisture, rainfall_detected=data.rainfall_detected,
        pore_pressure_kpa=data.pore_pressure_kpa, storage_mode=db_manager.mode
    )


@router.get("/sensors/latest")
async def get_latest_sensor_data():
    docs = list(db_manager.sensor_latest.find({}, {"_id": 0}))
    return [clean_document(d) for d in docs]
