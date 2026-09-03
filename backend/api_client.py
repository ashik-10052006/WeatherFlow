import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

from backend.config import settings

logger = logging.getLogger("weatherdata.api_client")

# WMO Weather interpretation codes (WW)
# Source: World Meteorological Organization & Open-Meteo Documentation
WMO_CODE_MAP: Dict[int, str] = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snow fall",
    73: "Moderate snow fall",
    75: "Heavy snow fall",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}


def decode_wmo_code(code: Optional[int]) -> str:
    """Map a WMO numerical weather code to a human-readable description."""
    if code is None:
        return "Unknown"
    return WMO_CODE_MAP.get(code, f"Weather Code {code}")


class WeatherApiClient:
    """Client for extracting current meteorological data from Open-Meteo REST API."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: Optional[int] = None,
        api_key: Optional[str] = None,
        provider: Optional[str] = None,
    ) -> None:
        self.provider = provider or settings.weather_api_provider
        self.api_key = api_key or settings.weather_api_key
        self.base_url = base_url or settings.weather_api_base_url
        self.timeout = timeout or settings.weather_api_timeout_seconds
        self.session = self._init_session()

    def _init_session(self) -> requests.Session:
        """Create a resilient requests session with exponential backoff retries."""
        session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1.0,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    def _fetch_from_weatherapi(
        self,
        latitude: float,
        longitude: float,
        location_id: Optional[int],
        city_name: str,
        country: str,
    ) -> Dict[str, Any]:
        """Fetch current weather from WeatherAPI.com using API key."""
        url = "http://api.weatherapi.com/v1/current.json"
        query_val = f"{latitude},{longitude}" if not city_name else city_name
        params = {
            "key": self.api_key,
            "q": query_val,
        }
        logger.info(f"Requesting weather from WeatherAPI.com for {city_name or query_val}")
        response = self.session.get(url, params=params, timeout=self.timeout)
        response.raise_for_status()
        data = response.json()

        curr = data.get("current", {})
        cond = curr.get("condition", {})

        return {
            "success": True,
            "location_id": location_id,
            "city_name": city_name or data.get("location", {}).get("name", ""),
            "country": country or data.get("location", {}).get("country", ""),
            "latitude": float(data.get("location", {}).get("lat", latitude)),
            "longitude": float(data.get("location", {}).get("lon", longitude)),
            "recorded_at": curr.get("last_updated"),
            "temperature_c": curr.get("temp_c"),
            "humidity_percent": curr.get("humidity"),
            "wind_speed_kmh": curr.get("wind_kph"),
            "weather_code": cond.get("code"),
            "weather_condition": cond.get("text"),
            "source": "weatherapi_com",
            "raw_response": data,
            "error": None,
        }

    def _fetch_from_openmeteo(
        self,
        latitude: float,
        longitude: float,
        location_id: Optional[int],
        city_name: str,
        country: str,
    ) -> Dict[str, Any]:
        """Fetch current weather from Open-Meteo REST API (keyless fallback)."""
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": float(latitude),
            "longitude": float(longitude),
            "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code",
            "timezone": "auto",
        }
        logger.info(f"Requesting weather from Open-Meteo for {city_name} ({latitude}, {longitude})")
        response = self.session.get(url, params=params, timeout=self.timeout)
        response.raise_for_status()
        data = response.json()

        current = data.get("current", {})
        weather_code = current.get("weather_code")

        return {
            "success": True,
            "location_id": location_id,
            "city_name": city_name,
            "country": country,
            "latitude": float(latitude),
            "longitude": float(longitude),
            "recorded_at": current.get("time"),
            "temperature_c": current.get("temperature_2m"),
            "humidity_percent": current.get("relative_humidity_2m"),
            "wind_speed_kmh": current.get("wind_speed_10m"),
            "weather_code": weather_code,
            "weather_condition": decode_wmo_code(weather_code),
            "source": "open_meteo",
            "raw_response": data,
            "error": None,
        }

    def fetch_weather(
        self,
        latitude: float,
        longitude: float,
        location_id: Optional[int] = None,
        city_name: str = "",
        country: str = "",
    ) -> Dict[str, Any]:
        """Fetch real-time weather using configured provider with automatic fallback."""
        try:
            if self.provider == "weatherapi" and self.api_key:
                try:
                    return self._fetch_from_weatherapi(
                        latitude, longitude, location_id, city_name, country
                    )
                except Exception as w_err:
                    logger.warning(
                        f"WeatherAPI.com request failed for {city_name}: {w_err}. Falling back to Open-Meteo."
                    )
            return self._fetch_from_openmeteo(
                latitude, longitude, location_id, city_name, country
            )
        except requests.exceptions.Timeout as e:
            logger.error(f"Timeout connecting to Weather API for {city_name}: {e}")
            return {
                "success": False,
                "location_id": location_id,
                "city_name": city_name,
                "country": country,
                "latitude": float(latitude),
                "longitude": float(longitude),
                "error": f"Connection timeout ({self.timeout}s): {str(e)}",
            }
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error {e.response.status_code} from Weather API: {e}")
            return {
                "success": False,
                "location_id": location_id,
                "city_name": city_name,
                "country": country,
                "latitude": float(latitude),
                "longitude": float(longitude),
                "error": f"HTTP error {e.response.status_code}: {str(e)}",
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error fetching weather for {city_name}: {e}")
            return {
                "success": False,
                "location_id": location_id,
                "city_name": city_name,
                "country": country,
                "latitude": float(latitude),
                "longitude": float(longitude),
                "error": f"Request failed: {str(e)}",
            }
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response for {city_name}: {e}")
            return {
                "success": False,
                "location_id": location_id,
                "city_name": city_name,
                "country": country,
                "latitude": float(latitude),
                "longitude": float(longitude),
                "error": f"Invalid JSON response: {str(e)}",
            }

    def fetch_by_query(self, query: str, location_id: Optional[int] = None) -> Dict[str, Any]:
        """Dynamically search and fetch weather for any city query worldwide."""
        query_clean = query.strip()
        if not query_clean:
            return {"success": False, "error": "City search query cannot be empty"}

        # 1. Try WeatherAPI.com if configured
        if self.api_key:
            try:
                url = "http://api.weatherapi.com/v1/current.json"
                params = {"key": self.api_key, "q": query_clean}
                resp = self.session.get(url, params=params, timeout=self.timeout)
                if resp.status_code == 200:
                    data = resp.json()
                    loc = data.get("location", {})
                    curr = data.get("current", {})
                    cond = curr.get("condition", {})
                    return {
                        "success": True,
                        "location_id": location_id,
                        "city_name": loc.get("name", query_clean),
                        "country": loc.get("country", ""),
                        "latitude": float(loc.get("lat", 0.0)),
                        "longitude": float(loc.get("lon", 0.0)),
                        "recorded_at": curr.get("last_updated"),
                        "temperature_c": curr.get("temp_c"),
                        "humidity_percent": curr.get("humidity"),
                        "wind_speed_kmh": curr.get("wind_kph"),
                        "weather_code": cond.get("code"),
                        "weather_condition": cond.get("text"),
                        "source": "weatherapi_com",
                        "raw_response": data,
                        "error": None,
                    }
            except Exception as e:
                logger.warning(f"WeatherAPI search for '{query_clean}' failed: {e}")

        # 2. Fallback to Open-Meteo Geocoding
        try:
            geo_url = "https://geocoding-api.open-meteo.com/v1/search"
            geo_params = {"name": query_clean, "count": 1, "language": "en", "format": "json"}
            geo_res = self.session.get(geo_url, params=geo_params, timeout=self.timeout)
            if geo_res.status_code == 200:
                geo_data = geo_res.json()
                results = geo_data.get("results")
                if results and len(results) > 0:
                    first = results[0]
                    lat = float(first["latitude"])
                    lon = float(first["longitude"])
                    city_name = first.get("name", query_clean)
                    country = first.get("country", "")
                    return self.fetch_weather(lat, lon, location_id, city_name, country)
        except Exception as e:
            logger.warning(f"Open-Meteo geocoding for '{query_clean}' failed: {e}")

        return {
            "success": False,
            "city_name": query_clean,
            "error": f"City '{query_clean}' was not found across weather providers.",
        }

    def fetch_multiple_locations(
        self, locations: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Fetch weather for an array of location dicts: [{location_id, city_name, country, latitude, longitude}]."""
        results = []
        for loc in locations:
            res = self.fetch_weather(
                latitude=float(loc["latitude"]),
                longitude=float(loc["longitude"]),
                location_id=loc.get("location_id"),
                city_name=loc.get("city_name", ""),
                country=loc.get("country", ""),
            )
            results.append(res)
        return results

    @staticmethod
    def load_sample_data() -> List[Dict[str, Any]]:
        """Load offline sample weather data for unit tests and local development fallback."""
        sample_path = Path(__file__).resolve().parent.parent / "data" / "sample_weather.json"
        with open(sample_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        results = []
        for item in data:
            curr = item.get("current", {})
            code = curr.get("weather_code")
            results.append(
                {
                    "success": True,
                    "location_id": item.get("location_id"),
                    "city_name": item.get("city_name"),
                    "country": item.get("country"),
                    "latitude": item.get("latitude"),
                    "longitude": item.get("longitude"),
                    "recorded_at": curr.get("time"),
                    "temperature_c": curr.get("temperature_2m"),
                    "humidity_percent": curr.get("relative_humidity_2m"),
                    "wind_speed_kmh": curr.get("wind_speed_10m"),
                    "weather_code": code,
                    "weather_condition": decode_wmo_code(code),
                    "raw_response": item,
                    "error": None,
                }
            )
        return results
