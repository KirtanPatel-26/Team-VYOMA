import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.analytics.fleet import FleetManager
from app.database.local import LocalDatabase
import tempfile
from pathlib import Path

client = TestClient(app)

def test_fleet_manager():
    fleet = FleetManager()
    stores = fleet.get_all_stores()
    assert len(stores) >= 3
    assert any(s["store_code"] == "STORE_001" for s in stores)

    success = fleet.set_active_store("STORE_002")
    assert success is True
    assert fleet.get_active_store()["city"] == "Mumbai"

    summary = fleet.get_fleet_summary({
        "traffic": {"current_customers": 10, "total_in": 100},
        "queue": {"queue_length": 2, "congestion": False},
        "stock": {"stock_health_score": 96.0},
        "business_impact": {"revenue_protected_today": 2500.0}
    })
    assert summary["total_locations"] >= 3
    assert summary["total_chain_active_customers"] > 10
    assert summary["total_chain_revenue_protected"] > 2500

def test_local_db_trends_and_weekly_summary():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_file = Path(tmpdir) / "test_retail.db"
        db = LocalDatabase(db_file)
        
        hourly = db.get_hourly_footfall_trends()
        assert len(hourly) == 14
        assert hourly[0]["hour"] == "09:00"

        daily = db.get_daily_footfall_trends()
        assert len(daily) == 7
        assert daily[0]["day"] == "Monday"

        weekly = db.get_weekly_summary()
        assert "total_weekly_footfall" in weekly
        assert weekly["total_weekly_footfall"] > 0

def test_api_privacy_endpoints():
    res_status = client.get("/api/privacy/status")
    assert res_status.status_code == 200
    data = res_status.json()
    assert "privacy_mode_enabled" in data
    assert "DPDP Act" in data["compliance"][0]

    res_toggle = client.post("/api/privacy/toggle", json={"privacy_mode": True})
    assert res_toggle.status_code == 200
    assert res_toggle.json()["privacy_mode_enabled"] is True

    # Revert to standard mode with blur
    client.post("/api/privacy/toggle", json={"privacy_mode": False, "blur_faces": True})

def test_api_fleet_and_trends_endpoints():
    res_fleet = client.get("/api/fleet/stores")
    assert res_fleet.status_code == 200
    assert len(res_fleet.json()["stores"]) >= 3

    res_switch = client.post("/api/fleet/switch", json={"store_code": "STORE_002"})
    assert res_switch.status_code == 200
    assert res_switch.json()["success"] is True

    # Switch back to STORE_001
    client.post("/api/fleet/switch", json={"store_code": "STORE_001"})

    res_summary = client.get("/api/fleet/summary")
    assert res_summary.status_code == 200
    assert "total_chain_active_customers" in res_summary.json()

    res_hourly = client.get("/api/traffic/trends/hourly")
    assert res_hourly.status_code == 200
    assert len(res_hourly.json()) == 14

    res_daily = client.get("/api/traffic/trends/daily")
    assert res_daily.status_code == 200
    assert len(res_daily.json()) == 7

def test_api_erp_webhook_and_weekly_reports():
    # Test ERP stock sync
    res_erp = client.post("/api/erp/webhook", json={
        "type": "STOCK_SYNC",
        "data": {"sku_id": "SKU001", "quantity": 10, "source_system": "Tally Prime ERP"}
    })
    assert res_erp.status_code == 200
    assert res_erp.json()["success"] is True

    # Test Weekly CSV report download
    res_csv = client.get("/api/reports/weekly/download")
    assert res_csv.status_code == 200
    assert "text/csv" in res_csv.headers["content-type"]
    assert "Weekly Footfall" in res_csv.text

    # Test Weekly PDF/HTML report
    res_pdf = client.get("/api/reports/weekly/pdf")
    assert res_pdf.status_code == 200
    assert "Weekly Executive Intelligence Brief" in res_pdf.text
