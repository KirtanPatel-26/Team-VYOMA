import os
import time
import json
import urllib.request
import urllib.error
from typing import Dict, Any, Optional

class WeatherService:
    """
    Real-time & Next-Day weather forecast service using Open-Meteo.
    - 100% Free, no proprietary API keys required.
    - Auto-detects store location from user's current PC (via Geo-IP), falling back to configured coordinates.
    - Offline-first cache (30-min TTL) to ensure zero edge disruption.
    - Used by DemandForecaster for weather-elasticity SKU sales predictions.
    """

    def __init__(
        self,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        city: Optional[str] = None,
        region: Optional[str] = None
    ):
        from app.config.settings import STORE_LAT, STORE_LON, STORE_CITY, STORE_REGION, STORE_COUNTRY
        self.lat = float(lat if lat is not None else os.getenv("STORE_LAT", str(STORE_LAT)))
        self.lon = float(lon if lon is not None else os.getenv("STORE_LON", str(STORE_LON)))
        self.city = city or os.getenv("STORE_CITY", STORE_CITY)
        self.region = region or os.getenv("STORE_REGION", STORE_REGION)
        self.country = os.getenv("STORE_COUNTRY", STORE_COUNTRY)
        self.detected_from = f"Store Location ({self.city}, {self.region})"
        self._cache = None
        self._last_fetch_time = 0
        self.cache_ttl_sec = 1800  # 30 mins

    def detect_pc_location(self, timeout: float = 2.5) -> bool:
        """
        Attempts to detect current PC physical location using Geo-IP lookup.
        Updates coordinates, city, and region seamlessly.
        """
        try:
            req = urllib.request.Request(
                "http://ip-api.com/json",
                headers={"User-Agent": "SmartRetail-AI/2.0"}
            )
            with urllib.request.urlopen(req, timeout=timeout) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode("utf-8"))
                    if data.get("status") == "success":
                        self.lat = round(float(data.get("lat", self.lat)), 4)
                        self.lon = round(float(data.get("lon", self.lon)), 4)
                        self.city = data.get("city", self.city)
                        self.region = data.get("regionName", self.region)
                        self.country = data.get("country", self.country)
                        self.detected_from = f"PC Geo-IP ({self.city}, {self.region})"
                        self._cache = None  # Invalidate cache to refetch for new location
                        return True
        except Exception:
            pass
        return False

    def _interpret_wmo_code(self, code: int) -> str:
        """Translates WMO weather code to clear human condition."""
        if code in [0, 1]:
            return "Clear / Sunny"
        elif code in [2, 3]:
            return "Partly Cloudy"
        elif code in [45, 48]:
            return "Foggy"
        elif code in [51, 53, 55, 61, 63, 65, 80, 81, 82]:
            return "Rainy / Showers"
        elif code in [95, 96, 99]:
            return "Thunderstorm"
        return "Normal / Moderate"

    def get_forecast(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Fetches current weather and tomorrow's forecast for the store's current location.
        Falls back to local cached or graceful defaults if offline.
        """
        now = time.time()
        if not force_refresh and self._cache and (now - self._last_fetch_time < self.cache_ttl_sec):
            return self._cache

        url = (
            f"https://api.open-meteo.com/v1/forecast"
            f"?latitude={self.lat}&longitude={self.lon}"
            f"&current=temperature_2m,relative_humidity_2m,precipitation,weather_code"
            f"&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code"
            f"&timezone=auto"
        )

        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "SmartRetail-AI/2.0"}
            )
            with urllib.request.urlopen(req, timeout=4) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode("utf-8"))
                    curr = data.get("current", {})
                    daily = data.get("daily", {})

                    curr_temp = curr.get("temperature_2m", 31.5)
                    curr_rh = curr.get("relative_humidity_2m", 62)
                    curr_code = curr.get("weather_code", 0)

                    # Tomorrow's forecast (index 1 in daily arrays)
                    tomorrow_max = daily.get("temperature_2m_max", [32.0, 33.0])
                    tomorrow_temp = tomorrow_max[1] if len(tomorrow_max) > 1 else 32.0
                    precip_prob_list = daily.get("precipitation_probability_max", [10, 20])
                    precip_prob = precip_prob_list[1] if len(precip_prob_list) > 1 else 15
                    t_code_list = daily.get("weather_code", [0, 0])
                    t_code = t_code_list[1] if len(t_code_list) > 1 else 0

                    is_hot = tomorrow_temp >= 30.0
                    is_rainy = precip_prob >= 40 or t_code in [51, 53, 55, 61, 63, 65, 80, 81, 82]
                    is_cold = tomorrow_temp <= 19.0

                    result = {
                        "source": "Open-Meteo API",
                        "status": "ONLINE",
                        "store_location": {
                            "city": self.city,
                            "region": self.region,
                            "country": self.country,
                            "lat": self.lat,
                            "lon": self.lon,
                            "detected_from": self.detected_from
                        },
                        "current": {
                            "temperature_c": curr_temp,
                            "humidity_pct": curr_rh,
                            "condition": self._interpret_wmo_code(curr_code),
                            "weather_code": curr_code
                        },
                        "tomorrow_forecast": {
                            "temperature_max_c": tomorrow_temp,
                            "precipitation_probability_pct": precip_prob,
                            "condition": self._interpret_wmo_code(t_code),
                            "is_hot_day": is_hot,
                            "is_rainy_day": is_rainy,
                            "is_cold_day": is_cold
                        },
                        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                    }
                    self._cache = result
                    self._last_fetch_time = now
                    return result
        except Exception as e:
            # Fallback to local deterministic synthetic weather if offline or network unavailable
            fallback = {
                "source": "Local Fallback (Offline Mode)",
                "status": "OFFLINE_CACHE",
                "error": str(e),
                "store_location": {
                    "city": self.city,
                    "region": self.region,
                    "country": self.country,
                    "lat": self.lat,
                    "lon": self.lon,
                    "detected_from": self.detected_from
                },
                "current": {
                    "temperature_c": 32.0,
                    "humidity_pct": 58,
                    "condition": "Warm / Sunny",
                    "weather_code": 0
                },
                "tomorrow_forecast": {
                    "temperature_max_c": 33.5,
                    "precipitation_probability_pct": 10,
                    "condition": "Clear / Sunny",
                    "is_hot_day": True,
                    "is_rainy_day": False,
                    "is_cold_day": False
                },
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            if self._cache:
                return self._cache
            return fallback
