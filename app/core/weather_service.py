"""天气工具（智能体可调用的实时天气能力）。

通过免费 Open-Meteo API 获取实地实时天气，无 API Key 依赖。
任何失败（断网 / 超时 / 解析错误）自动降级为中性占位，绝不阻断主链路。
后续接入真实智能体时，该服务可作为 Agent 的 weather 工具直接调用。
"""

import json
import time
import urllib.request
from datetime import datetime
from typing import Any


# WMO 天气代码 → (中文描述, 图标)
_WMO_MAP = {
    0: ('晴朗', '☀️'), 1: ('晴间多云', '🌤️'), 2: ('多云', '⛅'), 3: ('阴', '☁️'),
    45: ('有雾', '🌫️'), 48: ('有雾', '🌫️'),
    51: ('毛毛雨', '🌦️'), 53: ('毛毛雨', '🌦️'), 55: ('毛毛雨', '🌦️'),
    56: ('冻雨', '🌧️'), 57: ('冻雨', '🌧️'),
    61: ('小雨', '🌧️'), 63: ('中雨', '🌧️'), 65: ('大雨', '🌧️'),
    66: ('冻雨', '🌧️'), 67: ('冻雨', '🌧️'),
    71: ('小雪', '🌨️'), 73: ('中雪', '🌨️'), 75: ('大雪', '🌨️'),
    77: ('雪粒', '🌨️'),
    80: ('阵雨', '🌦️'), 81: ('阵雨', '🌧️'), 82: ('暴雨', '⛈️'),
    85: ('阵雪', '🌨️'), 86: ('阵雪', '🌨️'),
    95: ('雷阵雨', '⛈️'), 96: ('雷阵雨', '⛈️'), 99: ('雷阵雨', '⛈️'),
}

_CACHE_TTL_SECONDS = 300  # 5 分钟缓存，降低外部 API 请求频率


class WeatherService:
    """实时天气工具。"""

    API_URL = 'https://api.open-meteo.com/v1/forecast'
    TIMEOUT = 5
    DEFAULT_CITY = '上海'
    DEFAULT_LAT = 31.2304
    DEFAULT_LON = 121.4737

    _cache: dict[str, Any] = {}
    _cache_time = 0.0

    def get_weather(self, lat: float | None = None, lon: float | None = None) -> dict[str, Any]:
        lat = round(lat, 4) if lat else self.DEFAULT_LAT
        lon = round(lon, 4) if lon else self.DEFAULT_LON
        cache_key = f'{lat},{lon}'

        now = time.time()
        if now - self._cache_time < _CACHE_TTL_SECONDS and cache_key in self._cache:
            return self._cache[cache_key]

        try:
            data = self._fetch_open_meteo(lat, lon)
        except Exception:
            data = self._fallback()

        data['date'] = self._today_str()
        data['location'] = self.DEFAULT_CITY
        self._cache[cache_key] = data
        self._cache_time = now
        return data

    def _fetch_open_meteo(self, lat: float, lon: float) -> dict[str, Any]:
        url = (
            f'{self.API_URL}?latitude={lat}&longitude={lon}'
            f'&current=temperature_2m,weather_code&timezone=auto'
        )
        req = urllib.request.Request(url, headers={'User-Agent': 'silver-meal-demo/0.1'})
        with urllib.request.urlopen(req, timeout=self.TIMEOUT) as resp:
            payload = json.loads(resp.read().decode('utf-8'))

        current = payload.get('current') or {}
        temp = current.get('temperature_2m')
        code = current.get('weather_code')
        condition, icon = self._map_code(code)
        return {
            'temp': round(temp) if temp is not None else None,
            'condition': condition,
            'icon': icon,
            'source': 'open-meteo',
        }

    def _fallback(self) -> dict[str, Any]:
        return {
            'temp': None,
            'condition': '获取失败',
            'icon': '🌤️',
            'source': 'fallback',
        }

    def _map_code(self, code: int | None) -> tuple[str, str]:
        return _WMO_MAP.get(code, ('未知', '🌤️'))

    def _today_str(self) -> str:
        now = datetime.now()
        wd = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'][now.weekday()]
        return f'{now.month}月{now.day}日 {wd}'
