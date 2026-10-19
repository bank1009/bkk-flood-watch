"""
Unit tests for flood_engine.py verifying BMA Drainage Rule Engine standards.
"""

import pytest
from flood_engine import (
    evaluate_single_values,
    compute_rolling_3hr_cumulative,
    compute_max_3hr_window,
    analyze_series,
    format_time_label,
    build_banner_message,
    SIMULATION_SCENARIOS,
    BANGKOK_LOCATIONS,
    TIERS
)


class TestBMADrainageEngineTiers:
    """Tests all 4 risk tiers according to BMA Drainage rules."""

    def test_green_tier_normal(self):
        """GREEN: Peak hourly rain < 10 mm/hr AND 3-hr cumulative < 25 mm."""
        # Clean zero rain
        res0 = evaluate_single_values(0.0, 0.0)
        assert res0["code"] == "GREEN"
        assert res0["level"] == 1
        assert "ปกติ" in res0["title_th"]
        assert "การระบายน้ำปกติ สัญจรได้ตามปกติ" in res0["action_th"]

        # Light rain (5 mm/hr, 12 mm cumulative)
        res1 = evaluate_single_values(5.0, 12.0)
        assert res1["code"] == "GREEN"
        assert res1["level"] == 1

        # Borderline just below thresholds (9.9 mm/hr, 24.9 mm cumulative)
        res_border = evaluate_single_values(9.9, 24.9)
        assert res_border["code"] == "GREEN"

    def test_yellow_tier_watch(self):
        """YELLOW: Peak hourly rain between 10.0 - 35.0 mm/hr OR 3-hr cumulative between 25.0 - 50.0 mm."""
        # Triggered by hourly rain exactly at 10.0 mm/hr
        res_h_min = evaluate_single_values(10.0, 15.0)
        assert res_h_min["code"] == "YELLOW"
        assert res_h_min["level"] == 2
        assert "เฝ้าระวัง" in res_h_min["title_th"]
        assert "อาจมีน้ำขังผิวจราจร 5-10 ซม." in res_h_min["action_th"]

        # Triggered by hourly rain at 35.0 mm/hr
        res_h_max = evaluate_single_values(35.0, 20.0)
        assert res_h_max["code"] == "YELLOW"

        # Triggered by cumulative rain (peak only 8 mm, but 3-hr cumulative is 25.0 mm)
        res_c_min = evaluate_single_values(8.0, 25.0)
        assert res_c_min["code"] == "YELLOW"

        # Triggered by cumulative rain up to 50.0 mm
        res_c_max = evaluate_single_values(8.0, 50.0)
        assert res_c_max["code"] == "YELLOW"

    def test_orange_tier_warning(self):
        """ORANGE: Peak hourly rain between 35.1 - 60.0 mm/hr OR 3-hr cumulative between 50.1 - 80.0 mm."""
        # Triggered by hourly rain at 35.1 mm/hr
        res_h_min = evaluate_single_values(35.1, 20.0)
        assert res_h_min["code"] == "ORANGE"
        assert res_h_min["level"] == 3
        assert "แจ้งเตือนน้ำท่วมขัง" in res_h_min["title_th"]
        assert "ฝนตกหนักใกล้เต็มศักยภาพท่อระบายน้ำ กทม. (60 มม.)" in res_h_min["action_th"]

        # Triggered by hourly rain at 60.0 mm/hr (BMA Drainage Limit)
        res_h_max = evaluate_single_values(60.0, 40.0)
        assert res_h_max["code"] == "ORANGE"

        # Triggered by 3-hr cumulative between 50.1 - 80.0 mm even if hourly peak is lower (e.g. 25 mm/hr)
        res_c_min = evaluate_single_values(25.0, 50.1)
        assert res_c_min["code"] == "ORANGE"

        res_c_max = evaluate_single_values(25.0, 80.0)
        assert res_c_max["code"] == "ORANGE"

    def test_red_tier_critical(self):
        """RED: Peak hourly rain > 60.0 mm/hr OR 3-hr cumulative > 80.0 mm."""
        # Triggered by hourly rain > 60 mm/hr
        res_h = evaluate_single_values(60.1, 40.0)
        assert res_h["code"] == "RED"
        assert res_h["level"] == 4
        assert "วิกฤตน้ำท่วมฉับพลัน" in res_h["title_th"]
        assert "วิกฤต! ปริมาณฝนเกินขีดความสามารถในการระบายน้ำของ กทม." in res_h["action_th"]

        # Extreme downpour 75 mm/hr
        res_extreme = evaluate_single_values(75.0, 100.0)
        assert res_extreme["code"] == "RED"

        # Triggered by 3-hr cumulative > 80.0 mm (even if peak hourly was 30 mm/hr)
        res_c = evaluate_single_values(30.0, 80.1)
        assert res_c["code"] == "RED"


class TestSeriesAndWindowCalculations:
    """Tests 3-hr rolling cumulative and sliding window peak detection."""

    def test_rolling_3hr_cumulative(self):
        series = [10.0, 20.0, 30.0, 5.0, 0.0]
        # [0:3] = 60.0, [1:4] = 55.0, [2:5] = 35.0, [3:5] = 5.0, [4:5] = 0.0
        rolling = compute_rolling_3hr_cumulative(series)
        assert rolling[0] == 60.0
        assert rolling[1] == 55.0
        assert rolling[2] == 35.0
        assert rolling[3] == 5.0
        assert rolling[4] == 0.0

    def test_max_3hr_window(self):
        series = [0.0, 5.0, 25.0, 30.0, 20.0, 2.0, 0.0]
        window_info = compute_max_3hr_window(series)
        # 25 + 30 + 20 = 75.0 starting at index 2
        assert window_info["max_val"] == 75.0
        assert window_info["start_index"] == 2
        assert window_info["end_index"] == 4

    def test_analyze_series_summary_banner(self):
        # 24-hour rainfall mock with peak at index 4 (17:00)
        precip = [0.0, 1.0, 5.0, 15.0, 42.0, 20.0, 5.0] + [0.0] * 17
        times = [f"2026-10-19T{h:02d}:00" for h in range(13, 13 + 24)]

        analysis = analyze_series(precip, times, window_hours=24)
        assert analysis["peak_hourly"] == 42.0
        assert analysis["overall_risk"]["code"] == "ORANGE"
        assert analysis["next_6h_risk"]["code"] == "ORANGE"
        assert "แจ้งเตือนสีส้ม" in analysis["banner_message"]
        assert "42.0 มม./ชม." in analysis["banner_message"]
        assert len(analysis["hourly_breakdown"]) == 24


class TestSimulationPresets:
    """Verifies that all simulation scenarios evaluate to their intended tiers."""

    def test_normal_scenario(self):
        sc = SIMULATION_SCENARIOS["normal"]
        res = analyze_series(sc["precipitation"])
        assert res["overall_risk"]["code"] == "GREEN"

    def test_watch_scenario(self):
        sc = SIMULATION_SCENARIOS["watch"]
        res = analyze_series(sc["precipitation"])
        assert res["overall_risk"]["code"] == "YELLOW"

    def test_heavy_scenario(self):
        sc = SIMULATION_SCENARIOS["heavy"]
        res = analyze_series(sc["precipitation"])
        assert res["overall_risk"]["code"] == "ORANGE"

    def test_extreme_scenario(self):
        sc = SIMULATION_SCENARIOS["extreme"]
        res = analyze_series(sc["precipitation"])
        assert res["overall_risk"]["code"] == "RED"

    def test_cumulative_red_scenario(self):
        sc = SIMULATION_SCENARIOS["cumulative_red"]
        res = analyze_series(sc["precipitation"])
        assert res["overall_risk"]["code"] == "RED"


class TestLocationsData:
    """Verifies the 6 required Bangkok monitored zones."""

    def test_six_locations_present(self):
        assert len(BANGKOK_LOCATIONS) == 6
        loc_ids = [l["id"] for l in BANGKOK_LOCATIONS]
        assert "chatuchak" in loc_ids
        assert "dindaeng" in loc_ids
        assert "watthana" in loc_ids
        assert "bangkapi" in loc_ids
        assert "minburi" in loc_ids
        assert "bangkhae" in loc_ids

        # Verify lat/lon ranges are in Bangkok area
        for loc in BANGKOK_LOCATIONS:
            assert 13.5 <= loc["lat"] <= 14.0
            assert 100.3 <= loc["lon"] <= 100.9
