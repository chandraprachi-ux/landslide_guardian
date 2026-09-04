from fastapi import APIRouter
from ..services.weather_service import fetch_environmental_data, fetch_ner_forecast
from ..services.terrain_service import get_full_terrain_info

router = APIRouter()


@router.get("/environment/{lat}/{lon}")
async def get_environment_info(lat: float, lon: float, location_name: str = "Selected Location"):
    env = await fetch_environmental_data(lat, lon)
    terrain = get_full_terrain_info(location_name, lat, lon)
    env.slope = terrain["slope_deg"]
    env.elevation = terrain["elevation_m"]
    env.pore_pressure_kpa = 0.0
    return env


@router.get("/weather/ner")
async def get_ner_weather():
    return await fetch_ner_forecast()
