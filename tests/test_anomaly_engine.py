"""
Test Suite for AI-Powered Anomaly Detection & Custom Trigger Engine
Tests all 13 retail anomalies, rule triggers, acknowledge/resolve workflows,
and API endpoint operations.
"""

import pytest
import time
from fastapi.testclient import TestClient
from app.main import app
from app.analytics.anomaly_engine import RetailAnomalyEngine, AnomalySeverity, AnomalyStatus

@pytest.fixture
def engine():
    engine = RetailAnomalyEngine()
    engine.rules_config["cooldown_period_sec"] = 0 # Disable cooldown for fast unit tests
    return engine

@pytest.fixture
def client():
    return TestClient(app)


def test_anomaly_1_possible_shoplifting(engine):
    """Anomaly 1: Product count drops + no billing record + no inventory tx -> Critical Alert"""
    engine.previous_shelf_counts["SHELF_A:Cadbury Dairy Milk 50g"] = 10
    detected = engine.evaluate_all(
        detections=[],
        inventory_counts={"Cadbury Dairy Milk 50g": 6}, # 4 missing
        tracked_persons=[],
        queue_count=0,
        camera_health={},
        recent_pos_sales=[], # No sale
        recent_ledger_entries=[] # No ledger
    )
    assert len(detected) == 1
    a = detected[0]
    assert a["anomaly_type"] == "POSSIBLE_SHOPLIFTING"
    assert a["severity"] == AnomalySeverity.CRITICAL
    assert "Possible Shoplifting Detected" in a["description"]
    assert a["metadata"]["missing_units"] == 4


def test_anomaly_2_restricted_area_access(engine):
    """Anomaly 2: Person enters restricted warehouse zone -> High Severity"""
    detected = engine.evaluate_all(
        detections=[],
        inventory_counts={},
        tracked_persons=[{"track_id": 101, "zone": "ZONE_BACKROOM_RESTRICTED", "dwell_time": 10}],
        queue_count=0,
        camera_health={}
    )
    assert len(detected) == 1
    a = detected[0]
    assert a["anomaly_type"] == "RESTRICTED_AREA_ACCESS"
    assert a["severity"] == AnomalySeverity.HIGH
    assert a["person_id"] == 101


def test_anomaly_3_suspicious_loitering(engine):
    """Anomaly 3: Person loiters near shelf > 300s -> Medium Severity"""
    detected = engine.evaluate_all(
        detections=[],
        inventory_counts={},
        tracked_persons=[{"track_id": 202, "zone": "Jewelry_Shelf", "dwell_time": 350}],
        queue_count=0,
        camera_health={}
    )
    assert len(detected) == 1
    a = detected[0]
    assert a["anomaly_type"] == "SUSPICIOUS_LOITERING"
    assert a["severity"] == AnomalySeverity.MEDIUM
    assert a["metadata"]["dwell_time"] == 350


def test_anomaly_4_product_misplacement(engine):
    """Anomaly 4: Toothpaste in Soap Zone -> Medium Severity"""
    detected = engine.evaluate_all(
        detections=[{"name": "Colgate Total Toothpaste 120g", "zone": "Dove Soap Zone"}],
        inventory_counts={},
        tracked_persons=[],
        queue_count=0,
        camera_health={}
    )
    assert len(detected) == 1
    a = detected[0]
    assert a["anomaly_type"] == "PRODUCT_MISPLACEMENT"
    assert a["severity"] == AnomalySeverity.MEDIUM


def test_anomaly_5_rapid_inventory_removal(engine):
    """Anomaly 5: Inventory drops faster than normal (20 in 5m) -> High Severity"""
    now = time.time()
    engine.shelf_history["SHELF_A:Pringles Original 107g"] = [(now - 120, 25)]
    detected = engine.evaluate_all(
        detections=[],
        inventory_counts={"Pringles Original 107g": 5}, # 20 dropped
        tracked_persons=[],
        queue_count=0,
        camera_health={}
    )
    assert any(a["anomaly_type"] == "RAPID_INVENTORY_REMOVAL" for a in detected)
    a = next(a for a in detected if a["anomaly_type"] == "RAPID_INVENTORY_REMOVAL")
    assert a["severity"] == AnomalySeverity.HIGH


def test_anomaly_6_queue_congestion(engine):
    """Anomaly 6: Queue length > 10 customers -> Medium Severity"""
    detected = engine.evaluate_all(
        detections=[],
        inventory_counts={},
        tracked_persons=[],
        queue_count=12,
        camera_health={}
    )
    assert len(detected) == 1
    a = detected[0]
    assert a["anomaly_type"] == "QUEUE_CONGESTION"
    assert a["severity"] == AnomalySeverity.MEDIUM
    assert a["metadata"]["queue_length"] == 12


def test_anomaly_7_after_hours_activity(engine):
    """Anomaly 7: Store closed + Human detected -> Critical Alert"""
    engine.set_store_operating_status(False)
    detected = engine.evaluate_all(
        detections=[],
        inventory_counts={},
        tracked_persons=[{"track_id": 88, "zone": "AISLE_1", "dwell_time": 5}],
        queue_count=0,
        camera_health={}
    )
    assert len(detected) == 1
    a = detected[0]
    assert a["anomaly_type"] == "AFTER_HOURS_ACTIVITY"
    assert a["severity"] == AnomalySeverity.CRITICAL


def test_anomaly_8_camera_obstruction(engine):
    """Anomaly 8: Camera covered or blurred -> High Severity"""
    detected = engine.evaluate_all(
        detections=[],
        inventory_counts={},
        tracked_persons=[],
        queue_count=0,
        camera_health={"laplacian_var": 20.0, "is_blocked": True, "ssim": 0.3}
    )
    assert len(detected) == 1
    a = detected[0]
    assert a["anomaly_type"] == "CAMERA_OBSTRUCTION"
    assert a["severity"] == AnomalySeverity.HIGH


def test_anomaly_9_empty_shelf_event(engine):
    """Anomaly 9: Shelf count == 0 -> High Severity Out Of Stock"""
    detected = engine.evaluate_all(
        detections=[],
        inventory_counts={"Real Orange Juice 1L": 0},
        tracked_persons=[],
        queue_count=0,
        camera_health={}
    )
    assert len(detected) == 1
    a = detected[0]
    assert a["anomaly_type"] == "EMPTY_SHELF_EVENT"
    assert a["severity"] == AnomalySeverity.HIGH


def test_anomaly_10_unusual_customer_crowding(engine):
    """Anomaly 10: Crowd in aisle > 15 people -> Medium Severity"""
    crowd = [{"track_id": i, "zone": "Aisle_Snacks", "dwell_time": 20} for i in range(16)]
    detected = engine.evaluate_all(
        detections=[],
        inventory_counts={},
        tracked_persons=crowd,
        queue_count=0,
        camera_health={}
    )
    assert len(detected) == 1
    a = detected[0]
    assert a["anomaly_type"] == "UNUSUAL_CUSTOMER_CROWDING"
    assert a["metadata"]["occupancy"] == 16


def test_anomaly_11_high_dwell_time_hotspot(engine):
    """Anomaly 11: Multiple customers high dwell hotspot -> Medium Severity"""
    dwellers = [
        {"track_id": 1, "zone": "Display_Promo", "dwell_time": 150},
        {"track_id": 2, "zone": "Display_Promo", "dwell_time": 160},
        {"track_id": 3, "zone": "Display_Promo", "dwell_time": 140},
    ]
    detected = engine.evaluate_all(
        detections=[],
        inventory_counts={},
        tracked_persons=dwellers,
        queue_count=0,
        camera_health={}
    )
    assert len(detected) == 1
    a = detected[0]
    assert a["anomaly_type"] == "HIGH_DWELL_TIME_HOTSPOT"
    assert a["metadata"]["customer_count"] == 3


def test_anomaly_12_inventory_count_mismatch(engine):
    """Anomaly 12: Detected count != Expected count -> High Severity"""
    detected = engine.evaluate_all(
        detections=[],
        inventory_counts={"Fanta Orange 600ml": 2}, # expected is 10
        tracked_persons=[],
        queue_count=0,
        camera_health={}
    )
    assert len(detected) == 1
    a = detected[0]
    assert a["anomaly_type"] == "INVENTORY_COUNT_MISMATCH"
    assert a["severity"] == AnomalySeverity.HIGH


def test_anomaly_13_unusual_sales_vs_shelf_movement(engine):
    """Anomaly 13: Products disappear from shelf but sales remain low -> Critical Alert"""
    engine.previous_shelf_counts["SHELF_A:Amul Taaza 500ml"] = 20
    detected = engine.evaluate_all(
        detections=[],
        inventory_counts={"Amul Taaza 500ml": 10}, # 10 removed
        tracked_persons=[],
        queue_count=0,
        camera_health={},
        recent_pos_sales=[{"product_name": "Amul Taaza 500ml", "quantity": 1}] # only 1 billed
    )
    assert any(a["anomaly_type"] == "UNUSUAL_SALES_VS_SHELF_MOVEMENT" for a in detected)
    a = next(a for a in detected if a["anomaly_type"] == "UNUSUAL_SALES_VS_SHELF_MOVEMENT")
    assert a["severity"] == AnomalySeverity.CRITICAL


def test_api_anomalies_workflow(client):
    """Tests the full API workflow: simulate, stats, list, acknowledge, resolve"""
    # 1. Simulate all 13
    res_sim = client.post("/api/anomalies/simulate_all_13")
    assert res_sim.status_code == 200
    data_sim = res_sim.json()
    assert data_sim["success"] is True
    assert data_sim["simulated_anomalies_count"] >= 13

    # 2. Get Stats
    res_stats = client.get("/api/anomalies/stats")
    assert res_stats.status_code == 200
    stats = res_stats.json()["stats"]
    assert stats["total"] >= 13
    assert stats["critical"] >= 2 # Shoplifting, After hours, Sales vs shelf

    # 3. List
    res_list = client.get("/api/anomalies/list")
    assert res_list.status_code == 200
    anomalies = res_list.json()["anomalies"]
    assert len(anomalies) >= 13

    # 4. Acknowledge first anomaly
    target_id = anomalies[0]["anomaly_id"]
    res_ack = client.post(f"/api/anomalies/{target_id}/acknowledge", json={"operator": "Security Chief"})
    assert res_ack.status_code == 200
    assert res_ack.json()["status"] == "Acknowledged"

    # 5. Resolve
    res_res = client.post(f"/api/anomalies/{target_id}/resolve", json={"operator": "Store Manager", "notes": "Investigated and cleared"})
    assert res_res.status_code == 200
    assert res_res.json()["status"] == "Resolved"
