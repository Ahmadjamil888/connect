from __future__ import annotations

import requests
from config.config import _env_value

TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "city": {"type": "string"},
        "provider": {"type": "string", "enum": ["auto", "open-meteo", "weatherapi", "openweather", "tomorrow"]},
    },
}


def _api_key(*keys: str) -> str:
    return _env_value(*keys)


def _location_from_ip() -> tuple[float, float]:
    providers = [
        ("http://ip-api.com/json/", lambda data: (float(data["lat"]), float(data["lon"]))),
        ("https://ipwho.is/", lambda data: (float(data["latitude"]), float(data["longitude"]))),
    ]
    for url, parser in providers:
        try:
            response = requests.get(url, timeout=20)
            data = response.json()
            return parser(data)
        except Exception:
            continue
    return 40.7128, -74.0060


def _geocode_city(city: str) -> tuple[float, float, str]:
    response = requests.get(
        "https://geocoding-api.open-meteo.com/v1/search",
        params={"name": city, "count": 1, "language": "en", "format": "json"},
        timeout=20,
    )
    data = response.json()
    results = data.get("results") or []
    if not results:
        raise RuntimeError(f"City not found: {city}")
    first = results[0]
    return float(first["latitude"]), float(first["longitude"]), str(first["name"])


def _weather_code_description(code: int) -> str:
    descriptions = {
        0: "clear sky",
        1: "mainly clear",
        2: "partly cloudy",
        3: "overcast",
        45: "fog",
        48: "depositing rime fog",
        51: "light drizzle",
        53: "moderate drizzle",
        55: "dense drizzle",
        61: "slight rain",
        63: "moderate rain",
        65: "heavy rain",
        71: "slight snow",
        73: "moderate snow",
        75: "heavy snow",
        80: "rain showers",
        81: "moderate rain showers",
        82: "violent rain showers",
        95: "thunderstorm",
    }
    return descriptions.get(int(code), f"weather code {code}")


def _from_open_meteo(city: str) -> dict:
    if city:
        lat, lon, resolved_city = _geocode_city(city)
    else:
        lat, lon = _location_from_ip()
        resolved_city = "Current location"
    response = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,relative_humidity_2m,apparent_temperature,wind_speed_10m,weather_code",
        },
        timeout=20,
    )
    data = response.json()
    current = data["current"]
    return {
        "ok": True,
        "provider": "open-meteo",
        "city": resolved_city,
        "temp_c": current["temperature_2m"],
        "feels_like": current["apparent_temperature"],
        "humidity": current["relative_humidity_2m"],
        "wind_speed": current["wind_speed_10m"],
        "description": _weather_code_description(int(current["weather_code"])),
        "latitude": data.get("latitude"),
        "longitude": data.get("longitude"),
    }


def _from_weatherapi(city: str, api_key: str) -> dict:
    query = city or ",".join(str(value) for value in _location_from_ip())
    response = requests.get(
        "https://api.weatherapi.com/v1/current.json",
        params={"key": api_key, "q": query, "aqi": "no"},
        timeout=20,
    )
    data = response.json()
    if response.status_code != 200:
        raise RuntimeError(data.get("error", {}).get("message", "WeatherAPI lookup failed."))
    current = data["current"]
    return {
        "ok": True,
        "provider": "weatherapi",
        "city": data["location"]["name"],
        "temp_c": current["temp_c"],
        "feels_like": current["feelslike_c"],
        "humidity": current["humidity"],
        "wind_speed": current["wind_kph"],
        "description": current["condition"]["text"],
        "latitude": data["location"]["lat"],
        "longitude": data["location"]["lon"],
    }


def _from_openweather(city: str, api_key: str) -> dict:
    params = {"appid": api_key, "units": "metric"}
    if city:
        params["q"] = city
    else:
        lat, lon = _location_from_ip()
        params["lat"] = lat
        params["lon"] = lon
    response = requests.get("https://api.openweathermap.org/data/2.5/weather", params=params, timeout=20)
    data = response.json()
    if response.status_code != 200:
        raise RuntimeError(data.get("message", "OpenWeather lookup failed."))
    return {
        "ok": True,
        "provider": "openweather",
        "city": data["name"],
        "temp_c": data["main"]["temp"],
        "feels_like": data["main"]["feels_like"],
        "humidity": data["main"]["humidity"],
        "wind_speed": data["wind"]["speed"],
        "description": data["weather"][0]["description"],
        "latitude": data["coord"]["lat"],
        "longitude": data["coord"]["lon"],
    }


def _from_tomorrow(city: str, api_key: str) -> dict:
    location = city or ",".join(str(value) for value in _location_from_ip())
    response = requests.get(
        "https://api.tomorrow.io/v4/weather/realtime",
        params={"location": location, "apikey": api_key},
        timeout=20,
    )
    data = response.json()
    if response.status_code != 200:
        raise RuntimeError(data.get("message", "Tomorrow.io lookup failed."))
    values = data["data"]["values"]
    return {
        "ok": True,
        "provider": "tomorrow",
        "city": city or "Current location",
        "temp_c": values.get("temperature"),
        "feels_like": values.get("temperatureApparent"),
        "humidity": values.get("humidity"),
        "wind_speed": values.get("windSpeed"),
        "description": str(values.get("weatherCode")),
        "latitude": data.get("location", {}).get("lat"),
        "longitude": data.get("location", {}).get("lon"),
    }


def run(inputs, **_kwargs):
    city = str(inputs.get("city", "")).strip()
    provider = str(inputs.get("provider", "auto")).strip().lower() or "auto"
    weatherapi_key = _api_key("WEATHERAPI_KEY")
    openweather_key = _api_key("OPENWEATHER_API_KEY", "WEATHER_API_KEY")
    tomorrow_key = _api_key("TOMORROW_API_KEY")

    candidates = []
    if provider == "auto":
        candidates = [
            ("open-meteo", lambda: _from_open_meteo(city)),
            ("weatherapi", lambda: _from_weatherapi(city, weatherapi_key)) if weatherapi_key else None,
            ("openweather", lambda: _from_openweather(city, openweather_key)) if openweather_key else None,
            ("tomorrow", lambda: _from_tomorrow(city, tomorrow_key)) if tomorrow_key else None,
        ]
    else:
        mapping = {
            "open-meteo": lambda: _from_open_meteo(city),
            "weatherapi": lambda: _from_weatherapi(city, weatherapi_key),
            "openweather": lambda: _from_openweather(city, openweather_key),
            "tomorrow": lambda: _from_tomorrow(city, tomorrow_key),
        }
        if provider in {"weatherapi", "openweather", "tomorrow"} and not {"weatherapi": weatherapi_key, "openweather": openweather_key, "tomorrow": tomorrow_key}[provider]:
            return {"ok": False, "error": f"{provider} requires an API key."}
        candidates = [(provider, mapping[provider])] if provider in mapping else []

    errors = []
    for candidate in candidates:
        if candidate is None:
            continue
        name, fn = candidate
        try:
            return fn()
        except Exception as exc:
            errors.append(f"{name}: {exc}")
    return {"ok": False, "error": "Weather lookup failed.", "details": errors}
