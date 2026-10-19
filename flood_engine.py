"""
BKK Flood Watch - BMA Drainage Rule Engine
Evaluates flood risk levels across Bangkok districts based on
Bangkok Metropolitan Administration (BMA) drainage capacity standards.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime

# BMA Drainage capacity standard threshold tiers
TIERS = {
    "GREEN": {
        "code": "GREEN",
        "level": 1,
        "color": "#10B981",          # Emerald Green
        "bg_color": "rgba(16, 185, 129, 0.15)",
        "border_color": "#10B981",
        "badge_class": "bg-emerald-500/20 text-emerald-400 border-emerald-500/40",
        "title_th": "ปกติ",
        "title_en": "Normal Drainage",
        "status_name": "ระดับปกติ (Normal)",
        "action_th": "การระบายน้ำปกติ สัญจรได้ตามปกติ",
        "description_th": "ปริมาณฝนสะสมและฝนรายชั่วโมงอยู่ในเกณฑ์ปกติ ระบบท่อระบายน้ำ กทม. สามารถระบายน้ำได้ทันท่วงที",
        "bma_limit_pct": "< 17%"
    },
    "YELLOW": {
        "code": "YELLOW",
        "level": 2,
        "color": "#F59E0B",          # Amber Yellow
        "bg_color": "rgba(245, 158, 11, 0.15)",
        "border_color": "#F59E0B",
        "badge_class": "bg-amber-500/20 text-amber-400 border-amber-500/40",
        "title_th": "เฝ้าระวังน้ำรอการระบาย",
        "title_en": "Drainage Watch",
        "status_name": "เฝ้าระวัง (Watch)",
        "action_th": "ฝนปานกลางถึงหนัก อาจมีน้ำขังผิวจราจร 5-10 ซม. ในจุดลุ่มต่ำ",
        "description_th": "ฝนปานกลางถึงหนัก อาจเกิดน้ำรอระบายชั่วคราวบนผิวจราจร 5-10 ซม. ในซอยย่อยหรือจุดลุ่มต่ำ",
        "bma_limit_pct": "17% - 58%"
    },
    "ORANGE": {
        "code": "ORANGE",
        "level": 3,
        "color": "#F97316",          # Vibrant Orange
        "bg_color": "rgba(249, 115, 22, 0.15)",
        "border_color": "#F97316",
        "badge_class": "bg-orange-500/20 text-orange-400 border-orange-500/40",
        "title_th": "แจ้งเตือนน้ำท่วมขัง",
        "title_en": "Flood Warning",
        "status_name": "แจ้งเตือน (Warning)",
        "action_th": "ฝนตกหนักใกล้เต็มศักยภาพท่อระบายน้ำ กทม. (60 มม.) รถเล็กควรหลีกเลี่ยงซอยต่ำและอุโมงค์ทางลอด",
        "description_th": "ฝนตกหนักใกล้ขีดจำกัดความจุท่อระบายน้ำ กทม. (60 มม./ชม.) มีโอกาสเกิดน้ำท่วมขังบนถนนสายหลักและซอยลึก",
        "bma_limit_pct": "58% - 100%"
    },
    "RED": {
        "code": "RED",
        "level": 4,
        "color": "#EF4444",          # Critical Red
        "bg_color": "rgba(239, 68, 68, 0.15)",
        "border_color": "#EF4444",
        "badge_class": "bg-red-500/20 text-red-400 border-red-500/40",
        "title_th": "วิกฤตน้ำท่วมฉับพลัน",
        "title_en": "Critical Flood Risk",
        "status_name": "วิกฤต (Critical)",
        "action_th": "วิกฤต! ปริมาณฝนเกินขีดความสามารถในการระบายน้ำของ กทม. เสี่ยงน้ำท่วมสูงเกิน 25 ซม. งดใช้เส้นทางจุดเสี่ยง",
        "description_th": "ปริมาณฝนเกินขีดความสามารถในการระบายน้ำของระบบ กทม. อย่างสิ้นเชิง มีความเสี่ยงน้ำท่วมสูงเกิน 25 ซม. รถทุกชนิดสัญจรลำบาก",
        "bma_limit_pct": "> 100%"
    }
}

# Key flood-prone locations in Bangkok
BANGKOK_LOCATIONS = [
    {
        "id": "chatuchak",
        "name_th": "จตุจักร / ลาดพร้าว",
        "name_en": "Chatuchak / Lat Phrao",
        "lat": 13.8160,
        "lon": 100.5610,
        "hotspots": "แยกรัชดา-ลาดพร้าว, ถ.วิภาวดีรังสิต, ห้าแยกลาดพร้าว, ปากซอยลาดพร้าว 122",
        "drainage_basin": "ลุ่มน้ำคลองบางซื่อ / คลองลาดพร้าว (อุโมงค์ระบายน้ำคลองบางซื่อ)"
    },
    {
        "id": "dindaeng",
        "name_th": "ดินแดง / รัชดาภิเษก",
        "name_en": "Din Daeng / Ratchadaphisek",
        "lat": 13.7690,
        "lon": 100.5730,
        "hotspots": "ถ.ประชาสงเคราะห์, แยกโบสถ์แม่พระ, ถ.รัชดาภิเษกหน้าห้างเอสพลานาด, ซอยชานเมือง",
        "drainage_basin": "ลุ่มน้ำคลองสามเสน (สถานีสูบน้ำคลองสามเสน)"
    },
    {
        "id": "watthana",
        "name_th": "วัฒนา / สุขุมวิท - อโศก",
        "name_en": "Watthana / Sukhumvit - Asok",
        "lat": 13.7370,
        "lon": 100.5600,
        "hotspots": "สุขุมวิท 21 (อโศกมนตรี), สุขุมวิท 39, สุขุมวิท 71 (ปรีดีฯ), เอกมัย",
        "drainage_basin": "ลุ่มน้ำคลองเตย / คลองแสนแสบ (อุโมงค์ยักษ์พระรามเก้า-รามคำแหง)"
    },
    {
        "id": "bangkapi",
        "name_th": "บางกะปิ / รามคำแหง",
        "name_en": "Bang Kapi / Ramkhamhaeng",
        "lat": 13.7650,
        "lon": 100.6440,
        "hotspots": "แยกลำสาลี, หน้า ม.รามคำแหง, ถ.ศรีนครินทร์ช่วงคลองกะจะ, ถ.นวมินทร์",
        "drainage_basin": "ลุ่มน้ำคลองแสนแสบ / คลองจั่น (สถานีสูบน้ำแสนแสบ)"
    },
    {
        "id": "minburi",
        "name_th": "มีนบุรี (ทางระบายน้ำฝั่งตะวันออก)",
        "name_en": "Min Buri (Eastern Floodway)",
        "lat": 13.8130,
        "lon": 100.7480,
        "hotspots": "ตลาดมีนบุรี, ถ.สุวินทวงศ์, ถ.ร่มเกล้า, ประตูระบายน้ำแสนแสบมีนบุรี",
        "drainage_basin": "แนวฟลัดเวย์ฝั่งตะวันออก (คลองแสนแสบ-คลองประเวศฯ-อ่าวไทย)"
    },
    {
        "id": "bangkhae",
        "name_th": "บางแค / เพชรเกษม",
        "name_en": "Bang Khae / Phetkasem",
        "lat": 13.7120,
        "lon": 100.4070,
        "hotspots": "ถ.เพชรเกษม (ตลาดบางแค), ซอยเพชรเกษม 39, ถ.พุทธมณฑลสาย 2, คลองราชมนตรี",
        "drainage_basin": "ลุ่มน้ำฝั่งธนบุรี (คลองภาษีเจริญ / คลองทวีวัฒนา / คลองมหาชัย)"
    }
]


def evaluate_single_values(peak_hourly: float, cumulative_3hr: float) -> Dict[str, Any]:
    """
    Evaluates flood risk level based on BMA Drainage Rule Engine standards.

    Rules:
    - RED: Peak hourly rain > 60.0 mm/hr OR 3-hr cumulative > 80.0 mm
    - ORANGE: Peak hourly rain between 35.1 - 60.0 mm/hr OR 3-hr cumulative between 50.1 - 80.0 mm
    - YELLOW: Peak hourly rain between 10.0 - 35.0 mm/hr OR 3-hr cumulative between 25.0 - 50.0 mm
    - GREEN: Peak hourly rain < 10 mm/hr AND 3-hr cumulative < 25 mm
    """
    p = round(float(peak_hourly if peak_hourly is not None else 0.0), 2)
    c = round(float(cumulative_3hr if cumulative_3hr is not None else 0.0), 2)

    # Priority 1: Critical (RED)
    if p > 60.0 or c > 80.0:
        tier_code = "RED"
    # Priority 2: Warning (ORANGE)
    elif p > 35.0 or c > 50.0:
        tier_code = "ORANGE"
    # Priority 3: Watch (YELLOW)
    elif p >= 10.0 or c >= 25.0:
        tier_code = "YELLOW"
    # Priority 4: Normal (GREEN)
    else:
        tier_code = "GREEN"

    result = dict(TIERS[tier_code])
    result["peak_hourly"] = p
    result["cumulative_3hr"] = c
    return result


def compute_rolling_3hr_cumulative(precipitation_series: List[float]) -> List[float]:
    """
    Computes rolling 3-hour cumulative rainfall (forward sliding window [i, i+1, i+2]).
    For the last 2 hours, it sums whatever hours remain up to 3 hours.
    """
    n = len(precipitation_series)
    cumulative = []
    for i in range(n):
        window = precipitation_series[i : min(i + 3, n)]
        cumulative.append(round(sum(window), 2))
    return cumulative


def compute_max_3hr_window(precipitation_series: List[float]) -> Dict[str, Any]:
    """
    Finds the maximum 3-consecutive-hour cumulative rainfall in the series.
    """
    n = len(precipitation_series)
    if n == 0:
        return {"max_val": 0.0, "start_index": 0, "end_index": 0}
    if n < 3:
        return {"max_val": round(sum(precipitation_series), 2), "start_index": 0, "end_index": n - 1}

    max_val = -1.0
    best_start = 0
    for i in range(n - 2):
        window_sum = sum(precipitation_series[i : i + 3])
        if window_sum > max_val:
            max_val = window_sum
            best_start = i

    return {
        "max_val": round(max_val, 2),
        "start_index": best_start,
        "end_index": min(best_start + 2, n - 1)
    }


def analyze_series(
    precipitation_series: List[float],
    times: Optional[List[str]] = None,
    window_hours: int = 24
) -> Dict[str, Any]:
    """
    Analyzes hourly precipitation series over the next window_hours (default 24h),
    and computes both the 24-hour overall risk and the immediate 6-hour risk banner.
    """
    # Slice to desired window
    series = [float(x or 0.0) for x in precipitation_series[:window_hours]]
    n = len(series)

    if times is None:
        times = [f"+{i}h" for i in range(n)]
    else:
        times = times[:n]

    # Calculate metrics
    peak_hourly = max(series) if series else 0.0
    peak_idx = series.index(peak_hourly) if series else 0
    peak_time = times[peak_idx] if times else ""

    max_3hr_info = compute_max_3hr_window(series)
    max_3hr = max_3hr_info["max_val"]
    rolling_3hr = compute_rolling_3hr_cumulative(series)
    total_rain = round(sum(series), 2)

    # 24-Hour Overall Evaluation
    overall_risk = evaluate_single_values(peak_hourly, max_3hr)

    # Hourly evaluation breakdown
    hourly_evaluations = []
    for i in range(n):
        h_rain = series[i]
        c_3hr = rolling_3hr[i]
        h_eval = evaluate_single_values(h_rain, c_3hr)
        hourly_evaluations.append({
            "hour_index": i,
            "time": times[i],
            "precipitation": h_rain,
            "cumulative_3hr": c_3hr,
            "risk_code": h_eval["code"],
            "risk_level": h_eval["level"],
            "risk_color": h_eval["color"],
            "title_th": h_eval["title_th"]
        })

    # Next 6-Hour Window Evaluation (for Summary Alert Banner)
    next_6h_series = series[:6]
    next_6h_times = times[:6]
    peak_6h = max(next_6h_series) if next_6h_series else 0.0
    peak_6h_idx = next_6h_series.index(peak_6h) if next_6h_series else 0
    peak_6h_time = next_6h_times[peak_6h_idx] if next_6h_times else ""
    max_3hr_6h_info = compute_max_3hr_window(next_6h_series)
    max_3hr_6h = max_3hr_6h_info["max_val"]
    next_6h_risk = evaluate_single_values(peak_6h, max_3hr_6h)

    # Human-formatted alert banner string (Thai)
    formatted_peak_time = format_time_label(peak_6h_time)
    banner_message = build_banner_message(next_6h_risk, peak_6h, formatted_peak_time)

    return {
        "overall_risk": overall_risk,
        "next_6h_risk": next_6h_risk,
        "banner_message": banner_message,
        "peak_hourly": peak_hourly,
        "peak_time": peak_time,
        "peak_time_formatted": format_time_label(peak_time),
        "peak_6h_hourly": peak_6h,
        "peak_6h_time": peak_6h_time,
        "peak_6h_time_formatted": formatted_peak_time,
        "max_3hr_cumulative": max_3hr,
        "max_3hr_window": {
            "val": max_3hr,
            "start_time": times[max_3hr_info["start_index"]] if times else "",
            "end_time": times[max_3hr_info["end_index"]] if times else ""
        },
        "total_rain_24h": total_rain,
        "rolling_3hr": rolling_3hr,
        "hourly_breakdown": hourly_evaluations
    }


def format_time_label(time_str: str) -> str:
    """Formats ISO datetime string (e.g. 2026-10-19T17:00) into friendly Thai hour (17:00 น.)."""
    if not time_str:
        return "-"
    try:
        # Handles 2026-10-19T17:00 or similar
        if "T" in time_str:
            dt_part = time_str.split("T")[1][:5]
            return f"{dt_part} น."
        if ":" in time_str:
            return f"{time_str[:5]} น."
    except Exception:
        pass
    return time_str


def build_banner_message(risk_dict: Dict[str, Any], peak_val: float, peak_time: str) -> str:
    """Builds Thai summary alert banner string."""
    code = risk_dict.get("code", "GREEN")
    if code == "RED":
        return f"🚨 วิกฤตสีแดง! คาดว่าฝนตกหนักวิกฤตเวลา {peak_time} ปริมาณ {peak_val:.1f} มม./ชม. (เกินศักยภาพระบายน้ำ กทม. เสี่ยงน้ำท่วมสูง)"
    elif code == "ORANGE":
        return f"⚠️ แจ้งเตือนสีส้ม: คาดว่าฝนตกหนักเวลา {peak_time} ปริมาณ {peak_val:.1f} มม./ชม. (ใกล้เต็มขีดความสามารถท่อ กทม. 60 มม.)"
    elif code == "YELLOW":
        return f"🟡 เฝ้าระวังสีเหลือง: คาดว่ามีฝนตกปานกลางเวลา {peak_time} ปริมาณ {peak_val:.1f} มม./ชม. (อาจมีน้ำขังผิวจราจรในจุดลุ่มต่ำ)"
    else:
        return "🟢 ระดับปกติ (สีเขียว): ไม่พบกลุ่มฝนรุนแรงใน 6 ชั่วโมงข้างหน้า สภาพการระบายน้ำคล่องตัว สัญจรได้ตามปกติ"


# Mock datasets for Simulation Mode
SIMULATION_SCENARIOS = {
    "normal": {
        "id": "normal",
        "name_th": "จำลองสภาพปกติ (แดดออก / ฝนปรอย)",
        "name_en": "Simulate Normal",
        "description": "ฝนปรอยเล็กน้อย สูงสุด 2.5 มม./ชม. สภาพการระบายน้ำปกติ (สีเขียว)",
        "peak_target": 2.5,
        "precipitation": [0.0, 0.0, 0.5, 1.2, 2.5, 1.0, 0.5, 0.0, 0.0, 0.0, 0.0, 0.0,
                          0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    },
    "watch": {
        "id": "watch",
        "name_th": "จำลองฝนปานกลาง 22 มม. (เฝ้าระวัง)",
        "name_en": "Simulate Watch (22mm)",
        "description": "ฝนตกปานกลาง สะสม 3 ชม. 38 มม. เฝ้าระวังน้ำขังผิวจราจร 5-10 ซม. (สีเหลือง)",
        "peak_target": 22.0,
        "precipitation": [0.0, 2.0, 8.0, 22.0, 14.0, 5.0, 2.0, 0.5, 0.0, 0.0, 0.0, 0.0,
                          0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    },
    "heavy": {
        "id": "heavy",
        "name_th": "จำลองฝนตกหนัก 45 มม. (แจ้งเตือนส้ม)",
        "name_en": "Simulate 45mm Heavy Rain",
        "description": "ฝนตกหนัก 45 มม./ชม. (สะสม 3 ชม. 70 มม.) ใกล้ขีดจำกัดท่อระบายน้ำ กทม. 60 มม. (สีส้ม)",
        "peak_target": 45.0,
        "precipitation": [0.0, 1.0, 5.0, 10.0, 45.0, 15.0, 6.0, 2.0, 0.5, 0.0, 0.0, 0.0,
                          0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    },
    "extreme": {
        "id": "extreme",
        "name_th": "จำลองพายุวิกฤต 75 มม. (วิกฤตแดง)",
        "name_en": "Simulate 75mm Extreme Storm",
        "description": "ฝนตกหนักวิกฤต 75 มม./ชม. เกินขีดความสามารถท่อระบายน้ำ กทม. เสี่ยงน้ำท่วมฉับพลัน (สีแดง)",
        "peak_target": 75.0,
        "precipitation": [0.0, 2.0, 15.0, 40.0, 75.0, 35.0, 15.0, 5.0, 1.0, 0.0, 0.0, 0.0,
                          0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    },
    "cumulative_red": {
        "id": "cumulative_red",
        "name_th": "จำลองฝนแช่สะสม 3 ชม. เกิน 80 มม. (วิกฤตแดง)",
        "name_en": "Simulate 3-hr Cumulative > 80mm",
        "description": "ฝนตกแช่นาน 3 ชม. (30 + 30 + 25 = 85 มม.) แม้รายชั่วโมงไม่เกิน 60 มม. แต่สะสมเกิน 80 มม. เข้าเกณฑ์สีแดง",
        "peak_target": 30.0,
        "precipitation": [0.0, 5.0, 30.0, 30.0, 25.0, 10.0, 5.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                          0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    }
}
