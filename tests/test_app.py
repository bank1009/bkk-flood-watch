"""
Unit tests for Flask app API endpoints and simulation routing.
"""

import pytest
from app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_index_page(client):
    """Test that homepage loads successfully."""
    response = client.get("/")
    assert response.status_code == 200
    assert b"BKK Flood Watch" in response.data or b"<!DOCTYPE html>" in response.data


def test_api_locations(client):
    """Test that /api/locations returns 6 monitored districts."""
    response = client.get("/api/locations")
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert len(data["locations"]) == 6
    names = [loc["id"] for loc in data["locations"]]
    assert "chatuchak" in names
    assert "watthana" in names


def test_api_tiers(client):
    """Test /api/tiers endpoint."""
    response = client.get("/api/tiers")
    assert response.status_code == 200
    data = response.get_json()
    assert "GREEN" in data["tiers"]
    assert "YELLOW" in data["tiers"]
    assert "ORANGE" in data["tiers"]
    assert "RED" in data["tiers"]
    assert data["bma_drainage_limit_mm"] == 60.0


def test_api_forecast(client):
    """Test /api/forecast endpoint returns full weather and analysis data."""
    response = client.get("/api/forecast?location_id=chatuchak")
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["is_simulation"] is False
    assert "current" in data
    assert "analysis" in data
    assert "forecast_series" in data
    assert len(data["forecast_series"]["precipitation"]) == 24
    assert "banner_message" in data["analysis"]


def test_api_simulate_normal(client):
    """Test /api/simulate with normal scenario -> Green."""
    response = client.get("/api/simulate?scenario=normal&location_id=dindaeng")
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["is_simulation"] is True
    assert data["analysis"]["overall_risk"]["code"] == "GREEN"


def test_api_simulate_watch(client):
    """Test /api/simulate with watch scenario -> Yellow."""
    response = client.get("/api/simulate?scenario=watch&location_id=dindaeng")
    assert response.status_code == 200
    data = response.get_json()
    assert data["analysis"]["overall_risk"]["code"] == "YELLOW"


def test_api_simulate_heavy(client):
    """Test /api/simulate with 45mm heavy scenario -> Orange."""
    response = client.get("/api/simulate?scenario=heavy&location_id=watthana")
    assert response.status_code == 200
    data = response.get_json()
    assert data["analysis"]["overall_risk"]["code"] == "ORANGE"
    assert "แจ้งเตือนสีส้ม" in data["analysis"]["banner_message"]


def test_api_simulate_extreme(client):
    """Test /api/simulate with 75mm extreme storm -> Red."""
    response = client.get("/api/simulate?scenario=extreme&location_id=bangkapi")
    assert response.status_code == 200
    data = response.get_json()
    assert data["analysis"]["overall_risk"]["code"] == "RED"
    assert "วิกฤตสีแดง" in data["analysis"]["banner_message"]


def test_api_all_zones_status_live(client):
    """Test /api/all-zones-status endpoint returns all 6 zones with radius and tier data."""
    response = client.get("/api/all-zones-status")
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert len(data["zones"]) == 6
    for z in data["zones"]:
        assert "id" in z
        assert "name" in z
        assert "lat" in z
        assert "lon" in z
        assert "risk_tier" in z
        assert z["risk_tier"] in ["GREEN", "YELLOW", "ORANGE", "RED"]
        assert "radius_meters" in z
        assert z["radius_meters"] in [800, 1500, 2500, 3500]
        assert "peak_rain_mm" in z
        assert "cumulative_3hr_mm" in z
        assert "action_text" in z
        assert "action_th" in z
        assert "banner_message" in z
    assert data["summary"]["total_zones"] == 6


def test_api_all_zones_status_simulation_extreme(client):
    """Test /api/all-zones-status with scenario=extreme displays mixed Red/Orange tiers."""
    response = client.get("/api/all-zones-status?scenario=extreme")
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["is_simulation"] is True
    assert data["scenario"] == "extreme"
    assert data["summary"]["critical_count"] > 0
    # Chatuchak (factor 1.0 -> 75mm) should be RED with 3500m radius
    chatuchak = next(z for z in data["zones"] if z["id"] == "chatuchak")
    assert chatuchak["risk_tier"] == "RED"
    assert chatuchak["radius_meters"] == 3500

    # Bang Khae (factor 0.60 -> 45mm) should be ORANGE with 2500m radius
    bangkhae = next(z for z in data["zones"] if z["id"] == "bangkhae")
    assert bangkhae["risk_tier"] == "ORANGE"
    assert bangkhae["radius_meters"] == 2500


def test_api_all_zones_status_simulation_normal(client):
    """Test /api/all-zones-status with scenario=normal displays all Green 800m circles."""
    response = client.get("/api/all-zones-status?scenario=normal")
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["summary"]["normal_count"] == 6
    for z in data["zones"]:
        assert z["risk_tier"] == "GREEN"
        assert z["radius_meters"] == 800
        assert z["fill_opacity"] == 0.2


def test_api_check_location_missing_params(client):
    """Test /api/check-location validation for missing or invalid parameters."""
    # Missing both
    res = client.get("/api/check-location")
    assert res.status_code == 400
    assert "required" in res.get_json()["error"]

    # Missing lon
    res2 = client.get("/api/check-location?lat=13.75")
    assert res2.status_code == 400

    # Invalid coordinates
    res3 = client.get("/api/check-location?lat=invalid&lon=100.5")
    assert res3.status_code == 400

    # Out of range
    res4 = client.get("/api/check-location?lat=95.0&lon=100.5")
    assert res4.status_code == 400


def test_api_check_location_live(client):
    """Test /api/check-location returns dynamic coordinates analysis with required fields."""
    res = client.get("/api/check-location?lat=13.8500&lon=100.4800")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["lat"] == 13.85
    assert data["lon"] == 100.48
    assert "peak_rain_mm" in data
    assert "cumulative_3hr_mm" in data
    assert "risk_tier" in data
    assert data["risk_tier"] in ["GREEN", "YELLOW", "ORANGE", "RED"]
    assert "action_text" in data
    assert "radius_meters" in data
    assert "forecast_series" in data
    assert len(data["forecast_series"]["precipitation"]) == 24
    assert "hourly_forecast" in data
    assert len(data["hourly_forecast"]) == 24
    for h in data["hourly_forecast"]:
        assert "time" in h
        assert "precipitation" in h
        assert "cumulative_3hr_mm" in h
        assert "risk_tier" in h
    assert "peak_summary" in data
    assert "peak_rain_mm" in data["peak_summary"]
    assert "cumulative_3hr_mm" in data["peak_summary"]
    assert "risk_tier" in data["peak_summary"]


def test_api_check_location_simulation_extreme(client):
    """Test /api/check-location with scenario=extreme returns RED tier and 3500m radius."""
    res = client.get("/api/check-location?lat=13.8500&lon=100.4800&scenario=extreme")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["is_simulation"] is True
    assert data["risk_tier"] == "RED"
    assert data["radius_meters"] == 3500
    assert data["peak_rain_mm"] >= 60.0
    assert "วิกฤต" in data["action_text"]


def test_api_check_location_simulation_normal(client):
    """Test /api/check-location with scenario=normal returns GREEN tier and 800m radius."""
    res = client.get("/api/check-location?lat=13.8500&lon=100.4800&scenario=normal")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["risk_tier"] == "GREEN"
    assert data["radius_meters"] == 800
    assert data["peak_rain_mm"] < 10.0


def test_bangkok_boundary_geojson_endpoint(client):
    """Test that /static/bangkok_boundary.geojson returns a valid FeatureCollection with latitude clamped to >= 13.52."""
    res = client.get("/static/bangkok_boundary.geojson")
    assert res.status_code == 200
    data = res.get_json()
    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) > 0
    feature = data["features"][0]
    assert feature["type"] == "Feature"
    assert feature["properties"]["name"] == "Bangkok"
    assert feature["geometry"]["type"] in ["Polygon", "MultiPolygon"]
    assert len(feature["geometry"]["coordinates"]) > 0

    # Verify no coordinates dip below 13.44 into the Gulf of Thailand
    lats = []
    def _collect(coords):
        if len(coords) >= 2 and isinstance(coords[0], (int, float)):
            lats.append(coords[1])
        else:
            for c in coords:
                _collect(c)
    _collect(feature["geometry"]["coordinates"])
    assert min(lats) == 13.44


def test_ensure_bangkok_boundary_geojson_helper():
    """Test that ensure_bangkok_boundary_geojson returns an existing valid file path."""
    import os
    from app import ensure_bangkok_boundary_geojson
    path = ensure_bangkok_boundary_geojson()
    assert os.path.exists(path)
    assert os.path.getsize(path) > 1000


def test_footer_email_attribution(client):
    """Test that homepage footer renders clickable mailto link for chavalit.tira@gmail.com."""
    response = client.get("/")
    assert response.status_code == 200
    html = response.data.decode("utf-8")
    assert "chavalit.tira@gmail.com" in html
    assert 'href="mailto:chavalit.tira@gmail.com"' in html


