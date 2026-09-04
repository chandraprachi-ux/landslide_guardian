import asyncio
import time
import httpx

from ..models.schemas import EnvironmentalData

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
_CACHE = {}
_CACHE_TTL = 600
_SEMAPHORE = asyncio.Semaphore(4)  # Protect external rate limits with controlled concurrency

NER_LOCATIONS = [
    {"name": "Gangtok, Sikkim", "lat": 27.3389, "lon": 88.6065},
    {"name": "Shillong, Meghalaya", "lat": 25.5788, "lon": 91.8933},
    {"name": "Aizawl, Mizoram", "lat": 23.7271, "lon": 92.7176},
    {"name": "Kohima, Nagaland", "lat": 25.6740, "lon": 94.1086},
    {"name": "Itanagar, Arunachal Pradesh", "lat": 27.0844, "lon": 93.6053},
    {"name": "Guwahati, Assam", "lat": 26.1445, "lon": 91.7362},
    {"name": "Imphal, Manipur", "lat": 24.8170, "lon": 93.9368},
    {"name": "Agartala, Tripura", "lat": 23.8315, "lon": 91.2868},
]


async def _get(client, lat, lon, daily=False, retries=2):
    params = {
        "latitude": lat, "longitude": lon,
        "timezone": "auto",
        "current": "precipitation,relative_humidity_2m,temperature_2m,wind_speed_10m,soil_moisture_0_to_1cm",
        "hourly": "precipitation",
        "past_days": 3,
        "forecast_days": 7 if daily else 1,
    }
    if daily:
        params["daily"] = (
            "weather_code,temperature_2m_max,temperature_2m_min,"
            "precipitation_sum,precipitation_probability_max,wind_speed_10m_max"
        )
    async with _SEMAPHORE:
        for attempt in range(retries + 1):
            try:
                r = await client.get(OPEN_METEO_URL, params=params, timeout=12)
                r.raise_for_status()
                return r.json()
            except Exception as e:
                if attempt == retries:
                    raise
                await asyncio.sleep(0.5 * (2 ** attempt))


async def fetch_environmental_data(latitude: float, longitude: float) -> EnvironmentalData:
    key = ("env", round(latitude, 4), round(longitude, 4))
    cached = _CACHE.get(key)
    if cached and time.time() - cached[0] < _CACHE_TTL:
        return cached[1]

    try:
        async with httpx.AsyncClient() as client:
            data = await _get(client, latitude, longitude, daily=False)
        current = data.get("current", {})
        hourly = data.get("hourly", {})
        precip = hourly.get("precipitation", [])
        env = EnvironmentalData(
            rainfall_1h=float(current.get("precipitation", 0) or 0),
            rainfall_3h=float(sum(precip[-3:])) if precip else 0.0,
            rainfall_24h=float(sum(precip[-24:])) if precip else 0.0,
            rainfall_72h=float(sum(precip[-72:])) if precip else 0.0,
            rainfall_intensity=float(current.get("precipitation", 0) or 0),
            soil_moisture=float(current.get("soil_moisture_0_to_1cm", 0.3) or 0.3) * 100,
            humidity=float(current.get("relative_humidity_2m", 75) or 75),
            temperature=float(current.get("temperature_2m", 22) or 22),
            wind_speed=float(current.get("wind_speed_10m", 10) or 10),
            data_source="OPEN_METEO_LIVE",
        )
        _CACHE[key] = (time.time(), env)
        return env
    except Exception as exc:
        print("Weather API error:", exc)
        return EnvironmentalData(data_source="WEATHER_FALLBACK")


async def fetch_ner_forecast():
    async with httpx.AsyncClient() as client:
        tasks = [_get(client, x["lat"], x["lon"], daily=True) for x in NER_LOCATIONS]
        raw = await asyncio.gather(*tasks, return_exceptions=True)

    output = []
    for loc, data in zip(NER_LOCATIONS, raw):
        if isinstance(data, Exception):
            output.append({**loc, "status": "unavailable", "days": []})
            continue
        current = data.get("current", {})
        daily = data.get("daily", {})
        days = []
        n = len(daily.get("time", []))
        for i in range(min(7, n)):
            days.append({
                "date": daily["time"][i],
                "weather_code": daily.get("weather_code", [None]*n)[i],
                "temp_max": daily.get("temperature_2m_max", [None]*n)[i],
                "temp_min": daily.get("temperature_2m_min", [None]*n)[i],
                "rain_mm": daily.get("precipitation_sum", [None]*n)[i],
                "rain_probability": daily.get("precipitation_probability_max", [None]*n)[i],
                "wind_max_kmh": daily.get("wind_speed_10m_max", [None]*n)[i],
            })
        precip_24h = daily.get("precipitation_sum", [None]*n)[0] if n > 0 else current.get("precipitation")
        sm_val = current.get("soil_moisture_0_to_1cm")
        soil_moisture_pct = round(float(sm_val if sm_val is not None else 0.35) * 100, 1)
        output.append({
            **loc,
            "status": "live",
            "current": {
                "temperature": current.get("temperature_2m"),
                "precipitation": current.get("precipitation"),
                "precipitation_24h": precip_24h if precip_24h is not None else current.get("precipitation", 0),
                "humidity": current.get("relative_humidity_2m"),
                "wind": current.get("wind_speed_10m"),
                "soil_moisture": soil_moisture_pct,
            },
            "days": days,
        })
    return output
