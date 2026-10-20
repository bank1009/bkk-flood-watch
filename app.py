"""
BKK Flood Watch - Flask Application
Serves RESTful APIs and UI for Bangkok Weather Forecast & BMA Drainage Flood Risk Evaluation.
"""

__author__ = "Bank Chavalit Tirakitti"
__copyright__ = "Copyright (c) 2026 Bank Chavalit Tirakitti"

import os
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional

import requests
from flask import Flask, render_template, jsonify, request, send_from_directory

from flood_engine import (
    BANGKOK_LOCATIONS,
    TIERS,
    SIMULATION_SCENARIOS,
    analyze_series,
    format_time_label
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bkk_flood_watch")

app = Flask(__name__)
# Keep JSON keys in ordered fashion
app.json.sort_keys = False

# Bangkok Timezone (UTC+7)
BKK_TZ = timezone(timedelta(hours=7))


def ensure_bangkok_boundary_geojson() -> str:
    """
    Checks if static/bangkok_boundary.geojson exists.
    If not, fetches the official administrative boundary polygon from OpenStreetMap Nominatim API,
    wraps it in a valid GeoJSON FeatureCollection structure, and saves it.
    """
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    os.makedirs(static_dir, exist_ok=True)
    geojson_path = os.path.join(static_dir, "bangkok_boundary.geojson")

    if os.path.exists(geojson_path) and os.path.getsize(geojson_path) > 1000:
        return geojson_path

    logger.info("Fetching Bangkok administrative boundary from Nominatim API...")
    try:
        url = "https://nominatim.openstreetmap.org/search?state=Bangkok&country=Thailand&polygon_geojson=1&format=jsonv2"
        headers = {"User-Agent": "BKKFloodWatch/1.0 (contact@bkkfloodwatch.local)"}
        resp = requests.get(url, headers=headers, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        if data and isinstance(data, list) and len(data) > 0 and data[0].get("geojson"):
            feature_collection = {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {
                            "name": "Bangkok",
                            "name_th": "กรุงเทพมหานคร",
                            "admin_level": 4,
                            "display_name": data[0].get("display_name", "กรุงเทพมหานคร, ประเทศไทย")
                        },
                        "geometry": data[0]["geojson"]
                    }
                ]
            }
            with open(geojson_path, "w", encoding="utf-8") as f:
                json.dump(feature_collection, f, ensure_ascii=False, indent=2)
            logger.info("Saved bangkok_boundary.geojson (%d bytes)", os.path.getsize(geojson_path))
    except Exception as e:
        logger.warning("Could not fetch Bangkok boundary from Nominatim: %s", e)

    return geojson_path


# Ensure boundary exists at startup
ensure_bangkok_boundary_geojson()

# Weather code lookup
WEATHER_CODES = {
    0: {"desc_th": "ท้องฟ้าแจ่มใส", "desc_en": "Clear sky", "icon": "☀️"},
    1: {"desc_th": "ท้องฟ้าโปร่งเกือบทั้งหมด", "desc_en": "Mainly clear", "icon": "🌤️"},
    2: {"desc_th": "มีเมฆบางส่วน", "desc_en": "Partly cloudy", "icon": "⛅"},
    3: {"desc_th": "มีเมฆมาก / ครึ้มฟ้าครึ้มฝน", "desc_en": "Overcast", "icon": "☁️"},
    45: {"desc_th": "หมอกหนา", "desc_en": "Fog", "icon": "🌫️"},
    48: {"desc_th": "หมอกน้ำค้าง", "desc_en": "Depositing fog", "icon": "🌫️"},
    51: {"desc_th": "ฝนปรอยเล็กน้อย", "desc_en": "Light drizzle", "icon": "🌦️"},
    53: {"desc_th": "ฝนปรอยปานกลาง", "desc_en": "Moderate drizzle", "icon": "🌦️"},
    55: {"desc_th": "ฝนปรอยหนาแน่น", "desc_en": "Dense drizzle", "icon": "🌧️"},
    61: {"desc_th": "ฝนตกเล็กน้อย", "desc_en": "Slight rain", "icon": "🌦️"},
    63: {"desc_th": "ฝนตกปานกลาง", "desc_en": "Moderate rain", "icon": "🌧️"},
    65: {"desc_th": "ฝนตกหนัก", "desc_en": "Heavy rain", "icon": "🌧️"},
    80: {"desc_th": "ฝนซู่เล็กน้อย", "desc_en": "Slight rain showers", "icon": "🌦️"},
    81: {"desc_th": "ฝนซู่ปานกลาง", "desc_en": "Moderate rain showers", "icon": "🌧️"},
    82: {"desc_th": "ฝนซู่หนักรุนแรง", "desc_en": "Violent rain showers", "icon": "⛈️"},
    95: {"desc_th": "พายุฝนฟ้าคะนอง", "desc_en": "Thunderstorm", "icon": "⛈️"},
    96: {"desc_th": "พายุฝนฟ้าคะนองรุนแรงพร้อมลมกระโชก", "desc_en": "Thunderstorm with hail", "icon": "⛈️⚡"},
    99: {"desc_th": "พายุฝนฟ้าคะนองวิกฤต", "desc_en": "Severe thunderstorm", "icon": "🌩️⚡"}
}


def get_weather_info(code: Optional[int]) -> Dict[str, str]:
    if code is None:
        return {"desc_th": "ไม่มีข้อมูล", "desc_en": "Unknown", "icon": "🌤️"}
    return WEATHER_CODES.get(int(code), {"desc_th": "ฝนฟ้าคะนอง", "desc_en": "Precipitation", "icon": "🌧️"})


def find_location(location_id: str) -> Dict[str, Any]:
    for loc in BANGKOK_LOCATIONS:
        if loc["id"] == location_id:
            return loc
    return BANGKOK_LOCATIONS[0]


def fetch_open_meteo_forecast(lat: float, lon: float) -> Optional[Dict[str, Any]]:
    """
    Fetches real-time and 24-48h hourly forecast parameters from Open-Meteo API.
    """
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "temperature_2m,relative_humidity_2m,precipitation_probability,precipitation,weathercode",
        "timezone": "Asia/Bangkok",
        "forecast_days": 2
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            return response.json()
        logger.warning(f"Open-Meteo returned status {response.status_code}: {response.text}")
    except Exception as e:
        logger.error(f"Failed to fetch Open-Meteo data: {e}")
    return None


def generate_fallback_forecast(now_dt: datetime) -> Dict[str, Any]:
    """Generates realistic baseline forecast when external API is unreachable."""
    times = []
    temps = []
    humidity = []
    precip_prob = []
    precip = []
    weather_codes = []

    for i in range(24):
        dt = now_dt + timedelta(hours=i)
        times.append(dt.strftime("%Y-%m-%dT%H:00"))
        # Diurnal temperature cycle in Bangkok (28C - 34C)
        h = dt.hour
        temp = 32.0 - 4.0 * (1.0 if (h < 6 or h > 20) else 0.0) + (1.5 if 12 <= h <= 15 else 0.0)
        temps.append(round(temp, 1))
        humidity.append(75 if h >= 18 or h <= 8 else 62)
        # Afternoon tropical rain probability
        p_prob = 40 if 14 <= h <= 19 else 15
        precip_prob.append(p_prob)
        p_val = 1.5 if 15 <= h <= 17 else 0.0
        precip.append(p_val)
        weather_codes.append(61 if p_val > 0 else (2 if h >= 12 else 1))

    return {
        "hourly": {
            "time": times,
            "temperature_2m": temps,
            "relative_humidity_2m": humidity,
            "precipitation_probability": precip_prob,
            "precipitation": precip,
            "weathercode": weather_codes
        }
    }


@app.route("/")
def index():
    """Renders the main dashboard page."""
    return render_template(
        "index.html",
        locations=BANGKOK_LOCATIONS,
        tiers=TIERS,
        simulations=SIMULATION_SCENARIOS,
        google_maps_api_key=os.environ.get("GOOGLE_MAPS_API_KEY", "")
    )


@app.route("/static/bangkok_boundary.geojson")
def serve_bangkok_boundary():
    """Serves the Bangkok administrative boundary GeoJSON for GIS mapping."""
    ensure_bangkok_boundary_geojson()
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    return send_from_directory(static_dir, "bangkok_boundary.geojson", mimetype="application/geo+json")


@app.route("/api/locations")
def api_locations():
    """Returns the list of monitored Bangkok flood-prone zones."""
    return jsonify({
        "success": True,
        "locations": BANGKOK_LOCATIONS
    })


@app.route("/api/tiers")
def api_tiers():
    """Returns the BMA drainage flood risk evaluation standards."""
    return jsonify({
        "success": True,
        "tiers": TIERS,
        "bma_drainage_limit_mm": 60.0,
        "description": "เกณฑ์มาตรฐานประสิทธิภาพการระบายน้ำของกรุงเทพมหานคร (สำนักการระบายน้ำ กทม.)"
    })


@app.route("/api/check-location")
def api_check_location():
    """
    Dynamic Coordinate API Endpoint (Drop a Pin):
    Accepts lat and lon query parameters, fetches Open-Meteo real-time 24h forecast,
    runs BMA Drainage flood risk evaluation, and returns location-specific risk metrics.
    Supports optional ?scenario= override for Simulation Mode testing.
    """
    lat_str = request.args.get("lat", None)
    lon_str = request.args.get("lon", None)
    scenario_id = request.args.get("scenario", None)

    if lat_str is None or lon_str is None:
        return jsonify({
            "success": False,
            "error": "Query parameters 'lat' and 'lon' are required."
        }), 400

    try:
        lat = float(lat_str)
        lon = float(lon_str)
    except (ValueError, TypeError):
        return jsonify({
            "success": False,
            "error": "Query parameters 'lat' and 'lon' must be valid floating point numbers."
        }), 400

    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        return jsonify({
            "success": False,
            "error": "Latitude must be between -90 and 90, and longitude between -180 and 180."
        }), 400

    now_bkk = datetime.now(BKK_TZ)
    now_str = now_bkk.strftime("%Y-%m-%dT%H:00")
    is_simulation = bool(scenario_id and scenario_id in SIMULATION_SCENARIOS)

    if is_simulation:
        scenario = SIMULATION_SCENARIOS[scenario_id]
        base_precip = scenario["precipitation"]
        precip_slice = [round(val, 1) for val in base_precip]
        times_slice = [(now_bkk + timedelta(hours=i)).strftime("%Y-%m-%dT%H:00") for i in range(24)]

        analysis = analyze_series(precip_slice, times_slice, window_hours=24)
        risk_6h = analysis["next_6h_risk"]
        tier_code = risk_6h["code"]
        rad_cfg = RADIUS_TIER_CONFIG[tier_code]

        if tier_code == "RED":
            temp = 25.5
            humidity = 95
            precip_prob = 98
            wcode = 96
        elif tier_code == "ORANGE":
            temp = 27.0
            humidity = 88
            precip_prob = 85
            wcode = 65
        elif tier_code == "YELLOW":
            temp = 28.5
            humidity = 80
            precip_prob = 65
            wcode = 63
        else:
            temp = 32.5
            humidity = 60
            precip_prob = 20
            wcode = 1

        w_info = get_weather_info(wcode)
        temp_series = [round(temp + 2.0 - (p * 0.1), 1) for p in precip_slice]
        humidity_series = [min(99, int(humidity + (p * 0.4))) for p in precip_slice]
        precip_prob_series = [min(100, int(30 + p * 1.5)) if p > 0 else 15 for p in precip_slice]
        wcode_series = [wcode if p > 5 else (61 if p > 0 else 1) for p in precip_slice]
    else:
        raw_data = fetch_open_meteo_forecast(lat, lon)
        if not raw_data or "hourly" not in raw_data:
            raw_data = generate_fallback_forecast(now_bkk)

        hourly = raw_data.get("hourly", {})
        all_times = hourly.get("time", [])
        all_precip = hourly.get("precipitation", [])
        all_precip_prob = hourly.get("precipitation_probability", [])
        all_temp = hourly.get("temperature_2m", [])
        all_humidity = hourly.get("relative_humidity_2m", [])
        all_wcode = hourly.get("weathercode", [])

        start_idx = 0
        for idx, t in enumerate(all_times):
            if t >= now_str:
                start_idx = idx
                break

        end_idx = min(start_idx + 24, len(all_times))
        times_slice = all_times[start_idx:end_idx]
        precip_slice = all_precip[start_idx:end_idx]
        precip_prob_series = all_precip_prob[start_idx:end_idx] if all_precip_prob else [0] * len(times_slice)
        temp_series = all_temp[start_idx:end_idx] if all_temp else [30.0] * len(times_slice)
        humidity_series = all_humidity[start_idx:end_idx] if all_humidity else [70] * len(times_slice)
        wcode_series = all_wcode[start_idx:end_idx] if all_wcode else [0] * len(times_slice)

        while len(precip_slice) < 24:
            future_dt = now_bkk + timedelta(hours=len(times_slice))
            times_slice.append(future_dt.strftime("%Y-%m-%dT%H:00"))
            precip_slice.append(0.0)
            precip_prob_series.append(10)
            temp_series.append(30.0)
            humidity_series.append(70)
            wcode_series.append(1)

        analysis = analyze_series(precip_slice, times_slice, window_hours=24)
        risk_6h = analysis["next_6h_risk"]
        tier_code = risk_6h["code"]
        rad_cfg = RADIUS_TIER_CONFIG[tier_code]

        w_info = get_weather_info(wcode_series[0] if wcode_series else 0)

    current_summary = {
        "temperature": temp_series[0] if temp_series else 30.0,
        "humidity": humidity_series[0] if humidity_series else 70,
        "precipitation_probability": precip_prob_series[0] if precip_prob_series else 0,
        "precipitation_current": precip_slice[0] if precip_slice else 0.0,
        "weathercode": wcode_series[0] if wcode_series else 0,
        "weather_desc_th": w_info["desc_th"],
        "weather_desc_en": w_info["desc_en"],
        "weather_icon": w_info["icon"],
        "observed_at": times_slice[0] if times_slice else now_str,
        "observed_at_formatted": format_time_label(times_slice[0] if times_slice else now_str)
    }

    custom_location = {
        "id": "custom_pin",
        "name_th": f"พิกัดที่เลือก ({lat:.4f}, {lon:.4f})",
        "name_en": f"Selected Coordinates ({lat:.4f}, {lon:.4f})",
        "lat": lat,
        "lon": lon,
        "hotspots": f"พิกัด ละติจูด {lat:.4f}, ลองจิจูด {lon:.4f} (วิเคราะห์สภาพอากาศเฉพาะจุด)",
        "drainage_basin": "การประเมินอิงข้อมูลพยากรณ์ Open-Meteo ร่วมกับเกณฑ์ระบายน้ำ กทม."
    }

    # Full 24-hour hourly forecast array with time, precipitation, cumulative_3hr_mm, risk_tier
    hourly_forecast = []
    for i in range(len(times_slice)):
        hourly_forecast.append({
            "time": times_slice[i],
            "time_formatted": format_time_label(times_slice[i]),
            "precipitation": precip_slice[i],
            "cumulative_3hr_mm": analysis["rolling_3hr"][i],
            "risk_tier": analysis["hourly_breakdown"][i]["risk_code"]
        })

    # Overall peak summary
    peak_summary = {
        "peak_rain_mm": analysis["peak_hourly"],
        "peak_time": analysis["peak_time"],
        "peak_time_formatted": analysis["peak_time_formatted"],
        "cumulative_3hr_mm": analysis["max_3hr_cumulative"],
        "total_rain_24h": analysis["total_rain_24h"],
        "risk_tier": tier_code,
        "action_text": risk_6h["action_th"]
    }

    return jsonify({
        "success": True,
        "is_simulation": is_simulation,
        "lat": lat,
        "lon": lon,
        "peak_summary": peak_summary,
        "hourly_forecast": hourly_forecast,
        "peak_rain_mm": analysis["peak_hourly"],
        "peak_hourly": analysis["peak_hourly"],
        "peak_time_formatted": analysis["peak_time_formatted"],
        "peak_6h_hourly": analysis["peak_6h_hourly"],
        "peak_6h_time_formatted": analysis["peak_6h_time_formatted"],
        "cumulative_3hr_mm": analysis["max_3hr_cumulative"],
        "max_3hr_cumulative": analysis["max_3hr_cumulative"],
        "total_rain_24h": analysis["total_rain_24h"],
        "risk_tier": tier_code,
        "risk_level": risk_6h["level"],
        "risk_color": rad_cfg["color"],
        "risk_title_th": risk_6h["title_th"],
        "status_name": risk_6h["status_name"],
        "action_text": risk_6h["action_th"],
        "action_th": risk_6h["action_th"],
        "banner_message": analysis["banner_message"],
        "radius_meters": rad_cfg["radius_meters"],
        "fill_opacity": rad_cfg["fill_opacity"],
        "animation": rad_cfg["animation"],
        "location": custom_location,
        "current": current_summary,
        "analysis": analysis,
        "forecast_series": {
            "times": times_slice,
            "times_formatted": [format_time_label(t) for t in times_slice],
            "precipitation": precip_slice,
            "precipitation_probability": precip_prob_series,
            "temperature": temp_series,
            "humidity": humidity_series,
            "weathercode": wcode_series
        },
        "bma_limit": 60.0,
        "timestamp": now_bkk.isoformat()
    })


# Radius Map Configuration
RADIUS_TIER_CONFIG = {
    "GREEN": {
        "color": "#22c55e",
        "fill_opacity": 0.2,
        "radius_meters": 800,
        "animation": "none"
    },
    "YELLOW": {
        "color": "#eab308",
        "fill_opacity": 0.35,
        "radius_meters": 1500,
        "animation": "none"
    },
    "ORANGE": {
        "color": "#f97316",
        "fill_opacity": 0.45,
        "radius_meters": 2500,
        "animation": "pulse"
    },
    "RED": {
        "color": "#ef4444",
        "fill_opacity": 0.6,
        "radius_meters": 3500,
        "animation": "pulse-danger"
    }
}

# Microclimatic rain variation factors across Bangkok zones (±15-50% gradient)
ZONE_SIMULATION_FACTORS = {
    "chatuchak": 1.0,     # North storm center (100% intensity)
    "bangkapi": 1.08,     # Eastern canal corridor (+8% intensity)
    "dindaeng": 0.95,     # Inner city (-5% intensity)
    "watthana": 0.88,     # Sukhumvit corridor (-12% intensity)
    "minburi": 0.52,      # Eastern floodway outskirts (Orange buffer zone)
    "bangkhae": 0.48      # Thonburi southwestern zone (Orange buffer zone)
}


def fetch_all_zones_open_meteo() -> Optional[list]:
    """
    Fetches real-time forecast for all 6 Bangkok locations simultaneously
    using Open-Meteo multi-coordinate query.
    """
    lats = [str(loc["lat"]) for loc in BANGKOK_LOCATIONS]
    lons = [str(loc["lon"]) for loc in BANGKOK_LOCATIONS]
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": ",".join(lats),
        "longitude": ",".join(lons),
        "hourly": "temperature_2m,relative_humidity_2m,precipitation_probability,precipitation,weathercode",
        "timezone": "Asia/Bangkok",
        "forecast_days": 2
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list):
                return data
            elif isinstance(data, dict):
                return [data]
        logger.warning(f"Open-Meteo batch returned status {response.status_code}")
    except Exception as e:
        logger.error(f"Failed to fetch batch Open-Meteo data: {e}")
    return None


@app.route("/api/all-zones-status")
def api_all_zones_status():
    """
    Multi-Zone API Aggregation:
    Evaluates 6-hour and 24-hour flood risk for ALL 6 monitored Bangkok zones at once.
    Supports both real-time Open-Meteo data and Simulation Mode overrides (?scenario=heavy).
    """
    scenario_id = request.args.get("scenario", None)
    is_simulation = bool(scenario_id and scenario_id in SIMULATION_SCENARIOS)

    now_bkk = datetime.now(BKK_TZ)
    now_str = now_bkk.strftime("%Y-%m-%dT%H:00")

    zones_result = []

    if is_simulation:
        scenario = SIMULATION_SCENARIOS[scenario_id]
        base_precip = scenario["precipitation"]
        times_slice = [(now_bkk + timedelta(hours=i)).strftime("%Y-%m-%dT%H:00") for i in range(24)]

        for loc in BANGKOK_LOCATIONS:
            factor = ZONE_SIMULATION_FACTORS.get(loc["id"], 1.0)
            # Apply slight geographic variation (±15%) so map displays realistic mix of tiers
            zone_precip = [round(val * factor, 1) for val in base_precip]
            analysis = analyze_series(zone_precip, times_slice, window_hours=24)

            # Evaluate next 6h risk for radius map
            risk_6h = analysis["next_6h_risk"]
            tier_code = risk_6h["code"]
            rad_cfg = RADIUS_TIER_CONFIG[tier_code]

            zones_result.append({
                "id": loc["id"],
                "name": loc["name_th"],
                "name_th": loc["name_th"],
                "name_en": loc["name_en"],
                "lat": loc["lat"],
                "lon": loc["lon"],
                "hotspots": loc["hotspots"],
                "drainage_basin": loc["drainage_basin"],
                "peak_rain_mm": analysis["peak_hourly"],
                "peak_hourly": analysis["peak_hourly"],
                "peak_time_formatted": analysis["peak_time_formatted"],
                "peak_6h_hourly": analysis["peak_6h_hourly"],
                "peak_6h_time_formatted": analysis["peak_6h_time_formatted"],
                "cumulative_3hr_mm": analysis["max_3hr_cumulative"],
                "max_3hr_cumulative": analysis["max_3hr_cumulative"],
                "total_rain_24h": analysis["total_rain_24h"],
                "risk_tier": tier_code,
                "risk_level": risk_6h["level"],
                "risk_color": rad_cfg["color"],
                "risk_title_th": risk_6h["title_th"],
                "status_name": risk_6h["status_name"],
                "action_text": risk_6h["action_th"],
                "action_th": risk_6h["action_th"],
                "banner_message": analysis["banner_message"],
                "radius_meters": rad_cfg["radius_meters"],
                "fill_opacity": rad_cfg["fill_opacity"],
                "animation": rad_cfg["animation"]
            })
    else:
        batch_raw = fetch_all_zones_open_meteo()
        times_slice = [(now_bkk + timedelta(hours=i)).strftime("%Y-%m-%dT%H:00") for i in range(24)]

        for idx, loc in enumerate(BANGKOK_LOCATIONS):
            raw_zone = None
            if batch_raw and idx < len(batch_raw):
                raw_zone = batch_raw[idx]

            if not raw_zone or "hourly" not in raw_zone:
                raw_zone = generate_fallback_forecast(now_bkk)

            hourly = raw_zone.get("hourly", {})
            all_times = hourly.get("time", [])
            all_precip = hourly.get("precipitation", [])

            start_idx = 0
            for s_idx, t in enumerate(all_times):
                if t >= now_str:
                    start_idx = s_idx
                    break

            end_idx = min(start_idx + 24, len(all_times))
            z_precip = all_precip[start_idx:end_idx]
            z_times = all_times[start_idx:end_idx]

            while len(z_precip) < 24:
                z_precip.append(0.0)
                z_times.append((now_bkk + timedelta(hours=len(z_times))).strftime("%Y-%m-%dT%H:00"))

            analysis = analyze_series(z_precip, z_times, window_hours=24)
            risk_6h = analysis["next_6h_risk"]
            tier_code = risk_6h["code"]
            rad_cfg = RADIUS_TIER_CONFIG[tier_code]

            zones_result.append({
                "id": loc["id"],
                "name": loc["name_th"],
                "name_th": loc["name_th"],
                "name_en": loc["name_en"],
                "lat": loc["lat"],
                "lon": loc["lon"],
                "hotspots": loc["hotspots"],
                "drainage_basin": loc["drainage_basin"],
                "peak_rain_mm": analysis["peak_hourly"],
                "peak_hourly": analysis["peak_hourly"],
                "peak_time_formatted": analysis["peak_time_formatted"],
                "peak_6h_hourly": analysis["peak_6h_hourly"],
                "peak_6h_time_formatted": analysis["peak_6h_time_formatted"],
                "cumulative_3hr_mm": analysis["max_3hr_cumulative"],
                "max_3hr_cumulative": analysis["max_3hr_cumulative"],
                "total_rain_24h": analysis["total_rain_24h"],
                "risk_tier": tier_code,
                "risk_level": risk_6h["level"],
                "risk_color": rad_cfg["color"],
                "risk_title_th": risk_6h["title_th"],
                "status_name": risk_6h["status_name"],
                "action_text": risk_6h["action_th"],
                "action_th": risk_6h["action_th"],
                "banner_message": analysis["banner_message"],
                "radius_meters": rad_cfg["radius_meters"],
                "fill_opacity": rad_cfg["fill_opacity"],
                "animation": rad_cfg["animation"]
            })

    # Summary statistics across Bangkok
    critical_count = sum(1 for z in zones_result if z["risk_tier"] == "RED")
    warning_count = sum(1 for z in zones_result if z["risk_tier"] == "ORANGE")
    watch_count = sum(1 for z in zones_result if z["risk_tier"] == "YELLOW")
    normal_count = sum(1 for z in zones_result if z["risk_tier"] == "GREEN")

    max_tier = "GREEN"
    if critical_count > 0:
        max_tier = "RED"
    elif warning_count > 0:
        max_tier = "ORANGE"
    elif watch_count > 0:
        max_tier = "YELLOW"

    return jsonify({
        "success": True,
        "is_simulation": is_simulation,
        "scenario": scenario_id if is_simulation else None,
        "zones": zones_result,
        "summary": {
            "total_zones": len(zones_result),
            "max_risk_tier": max_tier,
            "critical_count": critical_count,
            "warning_count": warning_count,
            "watch_count": watch_count,
            "normal_count": normal_count
        },
        "timestamp": now_bkk.isoformat()
    })


@app.route("/api/simulations")
def api_simulations():
    """Returns preset simulation scenarios for testing."""
    return jsonify({
        "success": True,
        "scenarios": SIMULATION_SCENARIOS
    })


@app.route("/api/forecast")
def api_forecast():
    """
    Fetches real-time forecast and analyzes flood risk for the specified Bangkok zone.
    Query params:
        - location_id: e.g. 'chatuchak', 'dindaeng', etc.
    """
    location_id = request.args.get("location_id", "chatuchak")
    location = find_location(location_id)

    raw_data = fetch_open_meteo_forecast(location["lat"], location["lon"])
    now_bkk = datetime.now(BKK_TZ)

    if not raw_data or "hourly" not in raw_data:
        raw_data = generate_fallback_forecast(now_bkk)

    hourly = raw_data.get("hourly", {})
    all_times = hourly.get("time", [])
    all_precip = hourly.get("precipitation", [])
    all_precip_prob = hourly.get("precipitation_probability", [])
    all_temp = hourly.get("temperature_2m", [])
    all_humidity = hourly.get("relative_humidity_2m", [])
    all_wcode = hourly.get("weathercode", [])

    # Find the current hour index
    now_str = now_bkk.strftime("%Y-%m-%dT%H:00")
    start_idx = 0
    for idx, t in enumerate(all_times):
        if t >= now_str:
            start_idx = idx
            break

    # Extract 24-hour forecast slice
    end_idx = min(start_idx + 24, len(all_times))
    times_slice = all_times[start_idx:end_idx]
    precip_slice = all_precip[start_idx:end_idx]
    precip_prob_slice = all_precip_prob[start_idx:end_idx] if all_precip_prob else [0] * len(times_slice)
    temp_slice = all_temp[start_idx:end_idx] if all_temp else [30.0] * len(times_slice)
    humidity_slice = all_humidity[start_idx:end_idx] if all_humidity else [70] * len(times_slice)
    wcode_slice = all_wcode[start_idx:end_idx] if all_wcode else [0] * len(times_slice)

    # Fallback padding if slice length < 24
    while len(precip_slice) < 24:
        future_dt = now_bkk + timedelta(hours=len(times_slice))
        times_slice.append(future_dt.strftime("%Y-%m-%dT%H:00"))
        precip_slice.append(0.0)
        precip_prob_slice.append(10)
        temp_slice.append(30.0)
        humidity_slice.append(70)
        wcode_slice.append(1)

    # Run BMA Flood Risk Engine Analysis
    analysis = analyze_series(precip_slice, times_slice, window_hours=24)

    # Current weather summary
    curr_wcode = wcode_slice[0] if wcode_slice else 0
    w_info = get_weather_info(curr_wcode)

    current_summary = {
        "temperature": temp_slice[0] if temp_slice else 30.0,
        "humidity": humidity_slice[0] if humidity_slice else 70,
        "precipitation_probability": precip_prob_slice[0] if precip_prob_slice else 0,
        "precipitation_current": precip_slice[0] if precip_slice else 0.0,
        "weathercode": curr_wcode,
        "weather_desc_th": w_info["desc_th"],
        "weather_desc_en": w_info["desc_en"],
        "weather_icon": w_info["icon"],
        "observed_at": times_slice[0] if times_slice else now_str,
        "observed_at_formatted": format_time_label(times_slice[0] if times_slice else now_str)
    }

    return jsonify({
        "success": True,
        "is_simulation": False,
        "location": location,
        "current": current_summary,
        "analysis": analysis,
        "forecast_series": {
            "times": times_slice,
            "times_formatted": [format_time_label(t) for t in times_slice],
            "precipitation": precip_slice,
            "precipitation_probability": precip_prob_slice,
            "temperature": temp_slice,
            "humidity": humidity_slice,
            "weathercode": wcode_slice
        },
        "bma_limit": 60.0,
        "timestamp": now_bkk.isoformat()
    })


@app.route("/api/simulate", methods=["GET", "POST"])
def api_simulate():
    """
    Simulation Mode Endpoint:
    Allows user or automated tests to inject mock rainfall data into the backend rule engine.
    Query / body params:
        - scenario: 'normal', 'watch', 'heavy', 'extreme', 'cumulative_red'
        - location_id: e.g. 'chatuchak'
    """
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        scenario_id = data.get("scenario", "heavy")
        location_id = data.get("location_id", "chatuchak")
        custom_precip = data.get("custom_precipitation", None)
    else:
        scenario_id = request.args.get("scenario", "heavy")
        location_id = request.args.get("location_id", "chatuchak")
        custom_precip = None

    location = find_location(location_id)
    scenario = SIMULATION_SCENARIOS.get(scenario_id, SIMULATION_SCENARIOS["heavy"])

    factor = ZONE_SIMULATION_FACTORS.get(location_id, 1.0)
    if custom_precip and len(custom_precip) == 24:
        precip_slice = custom_precip
    else:
        precip_slice = [round(val * factor, 1) for val in scenario["precipitation"]]

    now_bkk = datetime.now(BKK_TZ)
    times_slice = [(now_bkk + timedelta(hours=i)).strftime("%Y-%m-%dT%H:00") for i in range(24)]

    # Run BMA Flood Risk Engine Analysis
    analysis = analyze_series(precip_slice, times_slice, window_hours=24)

    # Synthesize realistic weather metrics matching the rainfall intensity
    peak_hourly = analysis["peak_hourly"]
    overall_code = analysis["overall_risk"]["code"]

    if overall_code == "RED":
        temp = 25.5
        humidity = 95
        precip_prob = 98
        wcode = 96
    elif overall_code == "ORANGE":
        temp = 27.0
        humidity = 88
        precip_prob = 85
        wcode = 65
    elif overall_code == "YELLOW":
        temp = 28.5
        humidity = 80
        precip_prob = 65
        wcode = 63
    else:
        temp = 32.5
        humidity = 60
        precip_prob = 20
        wcode = 1

    w_info = get_weather_info(wcode)

    current_summary = {
        "temperature": temp,
        "humidity": humidity,
        "precipitation_probability": precip_prob,
        "precipitation_current": precip_slice[0],
        "weathercode": wcode,
        "weather_desc_th": w_info["desc_th"],
        "weather_desc_en": w_info["desc_en"],
        "weather_icon": w_info["icon"],
        "observed_at": times_slice[0],
        "observed_at_formatted": format_time_label(times_slice[0])
    }

    # Generate temperature & humidity curves for chart
    temp_series = [round(temp + 2.0 - (p * 0.1), 1) for p in precip_slice]
    humidity_series = [min(99, int(humidity + (p * 0.4))) for p in precip_slice]
    precip_prob_series = [min(100, int(30 + p * 1.5)) if p > 0 else 15 for p in precip_slice]

    return jsonify({
        "success": True,
        "is_simulation": True,
        "scenario": scenario,
        "location": location,
        "current": current_summary,
        "analysis": analysis,
        "forecast_series": {
            "times": times_slice,
            "times_formatted": [format_time_label(t) for t in times_slice],
            "precipitation": precip_slice,
            "precipitation_probability": precip_prob_series,
            "temperature": temp_series,
            "humidity": humidity_series,
            "weathercode": [wcode if p > 5 else (61 if p > 0 else 1) for p in precip_slice]
        },
        "bma_limit": 60.0,
        "timestamp": now_bkk.isoformat()
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
