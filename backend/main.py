import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .database.mongodb import db_manager
from .routes import alerts, assistant, dataset, environment, locations, monitor, risk, sensors, sos, admin, auth, pipeline

logging.basicConfig(level=logging.INFO)

# Automatic background monitoring: recompute risk for all NER locations on an
# interval and auto-dispatch SOS emails to registered residents when a region
# reaches HIGH/CRITICAL.
_monitor_task = None


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global _monitor_task
    from .services.monitor import background_monitor_loop
    _monitor_task = asyncio.create_task(background_monitor_loop())
    logging.getLogger(__name__).info("Automatic monitoring loop scheduled.")
    yield
    if _monitor_task:
        _monitor_task.cancel()
        logging.getLogger(__name__).info("Automatic monitoring loop stopped.")


app = FastAPI(
    title="Landslide Guardian API",
    description="Software-only SIH landslide risk monitoring with live weather, ML and future sensor compatibility.",
    version="2.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=False,
    allow_methods=["*"], allow_headers=["*"]
)

app.include_router(locations.router, prefix="/api", tags=["Locations"])
app.include_router(environment.router, prefix="/api", tags=["Weather & Environment"])
app.include_router(risk.router, prefix="/api", tags=["Risk ML Engine"])
app.include_router(sensors.router, prefix="/api", tags=["Future Sensor Interface"])
app.include_router(dataset.router, prefix="/api", tags=["Dataset"])
app.include_router(alerts.router, prefix="/api", tags=["Alerts"])
app.include_router(sos.router, prefix="/api", tags=["Citizen Email Alerts"])
app.include_router(admin.router, prefix="/api", tags=["Admin Authentication"])
app.include_router(assistant.router, prefix="/api", tags=["Assistant"])
app.include_router(monitor.router, prefix="/api", tags=["Automatic Monitoring"])
app.include_router(pipeline.router, prefix="/api", tags=["Live Rainfall → Pore Pressure → Threshold Pipeline"])
app.include_router(auth.router, prefix="/api", tags=["Email OTP Verification"])

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


@app.get("/api/health")
async def health_check():
    connected = db_manager.ping()
    return {
        "status": "healthy",
        "database": "mongodb_atlas" if connected else "in_memory_demo",
        "database_connected": connected,
        "system": "Landslide Guardian API",
        "mode": "Software-only live weather + ML + future sensor interface",
    }


@app.get("/api/config")
async def config():
    from .services.monitor import get_monitoring_state
    from .services.region_config import get_all_regions
    from .services.notification_service import _smtp_configured
    mon = get_monitoring_state()
    return {
        "api_version": app.version,
        "storage_mode": db_manager.mode,
        "hardware_ready": False,
        "future_sensor_interface": True,
        "email_alerts": True,
        "email_otp_verification": True,
        "smtp_configured": _smtp_configured(),
        "automatic_monitoring": mon["enabled"],
        "monitor_interval_seconds": mon["interval_seconds"],
        "sos_cooldown_seconds": mon["dispatch_cooldown_seconds"],
        "verified_only_sos": True,
        "regions": len(get_all_regions()),
        "weather_source": "Open-Meteo (https://api.open-meteo.com/v1/forecast) — reused from existing project",
        "tilt": "Hardware Sensor Only — never simulated",
    }


@app.get("/", include_in_schema=False)
async def frontend_home():
    return FileResponse(FRONTEND_DIR / "index.html")


app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
