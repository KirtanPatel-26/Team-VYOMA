import time
import pytest
import numpy as np
from pathlib import Path

from app.theft.config import TheftConfig
from app.theft.zones import StoreZone, StoreZoneManager
from app.theft.interaction import InteractionTracker, PersonState
from app.theft.product_tracker import ProductRemovalTracker, TrackedProduct
from app.theft.risk_engine import RiskScoringEngine, RiskLevel
from app.theft.engine import TheftDetectionEngine, SNAPSHOT_DIR
from app.detection.results import Detection
from app.database.local import LocalDatabase

class DummyDetection:
    def __init__(self, class_name, bbox, track_id=None, sku_id=None, product_name=None, confidence=0.90):
        self.class_name = class_name
        self.bbox = bbox
        self.track_id = track_id
        self.sku_id = sku_id
        self.product_name = product_name
        self.confidence = confidence

def test_theft_config():
    cfg = TheftConfig()
    assert cfg.enabled is True
    assert cfg.theft_risk_threshold == 60
    assert cfg.high_risk_threshold == 80
    assert cfg.product_missing_seconds == 2.0
    
    d = cfg.to_dict()
    assert d["score_pickup"] == 20
    assert d["score_disappeared"] == 25
    assert d["score_checkout"] == -50

    cfg2 = TheftConfig.from_dict({"theft_risk_threshold": 65, "score_pickup": 25})
    assert cfg2.theft_risk_threshold == 65
    assert cfg2.score_pickup == 25

def test_store_zones():
    zm = StoreZoneManager(camera_id="camera_test")
    assert len(zm.zones) >= 4
    
    # Check Shelf A coordinate [40, 40, 520, 270]
    shelf_a = zm.get_zone_at(200, 150)
    assert shelf_a is not None
    assert shelf_a.zone_type == "SHELF_ZONE"

    # Check Exit zone coordinate between Shelf C & Billing Counter [760, 270, 1280, 359]
    exit_z = zm.get_zone_at(1000, 310)
    assert exit_z is not None
    assert exit_z.zone_type == "EXIT_ZONE"

    # Check Checkout zone [830, 360, 1240, 680]
    q_z = zm.get_zone_at(900, 500)
    assert q_z is not None
    assert q_z.zone_type == "CHECKOUT_ZONE"

    # Out of zone
    none_z = zm.get_zone_at(600, 10)
    assert none_z is None
    assert zm.get_zone_name_at(600, 10) == "Aisle / Common Area"

def test_interaction_tracker():
    zm = StoreZoneManager(camera_id="camera_test")
    it = InteractionTracker(zm)
    t0 = 1000.0

    # Person #101 enters Shelf A ([40, 40, 520, 270])
    dets = [DummyDetection("person", (100, 100, 180, 240), track_id=101)]
    persons = it.update(dets, timestamp=t0)
    assert 101 in persons
    assert persons[101].active_shelf_id is not None
    assert persons[101].shelf_dwell_time == 0.0

    # Person stays for 2 seconds
    t1 = t0 + 2.0
    dets2 = [DummyDetection("person", (105, 105, 185, 245), track_id=101)]
    persons = it.update(dets2, timestamp=t1)
    assert persons[101].shelf_dwell_time >= 2.0

    # Interaction tracker can find person near shelf
    p_near = it.get_person_near_shelf(persons[101].active_shelf_id)
    assert p_near is not None
    assert p_near.person_id == 101

def test_temporal_product_removal_and_return():
    zm = StoreZoneManager(camera_id="camera_test")
    it = InteractionTracker(zm)
    prt = ProductRemovalTracker(zm, it, missing_seconds_threshold=1.5, min_shelf_interaction_sec=1.0)
    t0 = 1000.0

    # 1. Product is visible on Shelf A
    shelf_a_id = zm.get_zone_at(200, 150).zone_id
    prod_dets = [DummyDetection("bottle", (120, 140, 160, 200), sku_id="SKU001", product_name="Fanta Orange")]
    removed, returned = prt.update(prod_dets, timestamp=t0)
    assert len(removed) == 0
    assert len(returned) == 0
    assert len(prt.tracked_products) == 1

    # 2. Person arrives and interacts for 1.2s
    person_dets = [DummyDetection("person", (100, 100, 180, 240), track_id=101)]
    it.update(person_dets, timestamp=t0)
    it.update(person_dets, timestamp=t0 + 1.2)

    # 3. Product disappears temporarily for 0.5s (flicker test)
    removed, returned = prt.update([], timestamp=t0 + 1.5)
    # Must NOT trigger removal yet! (Flicker immunity)
    assert len(removed) == 0

    # 4. Product remains missing for 2.5s (> 1.5s threshold)
    removed, returned = prt.update([], timestamp=t0 + 3.0)
    assert len(removed) == 1
    assert removed[0]["event_type"] == "POTENTIAL_PRODUCT_REMOVAL"
    assert removed[0]["sku_id"] == "SKU001"
    assert removed[0]["person_id"] == 101

    # 5. Product is put back on shelf -> Reappears!
    removed, returned = prt.update(prod_dets, timestamp=t0 + 5.0)
    assert len(removed) == 0
    assert len(returned) == 1
    assert returned[0]["event_type"] == "PRODUCT_RETURNED_TO_SHELF"
    assert returned[0]["sku_id"] == "SKU001"

def test_risk_scoring_engine():
    cfg = TheftConfig()
    engine = RiskScoringEngine(cfg)
    profile = engine.get_or_create_profile(101)
    assert profile.risk_score == 0
    assert profile.risk_level == RiskLevel.NORMAL

    # Step 1: Shelf pickup (+20)
    zm = StoreZoneManager(camera_id="camera_test")
    p_state = PersonState(101, (200, 150), 1000.0)
    p_state.active_shelf_id = "SHELF_A"
    p_state.shelf_dwell_time = 2.0
    engine.process_person_movement(p_state, 1002.0)
    assert profile.risk_score == 20
    assert profile.risk_level == RiskLevel.NORMAL

    # Step 2: Product disappears (+25) -> Total = 45 (LOW)
    engine.process_product_removal_event({
        "person_id": 101,
        "product_name": "Fanta Orange",
        "sku_id": "SKU001",
        "shelf_id": "SHELF_A"
    })
    assert profile.risk_score == 45
    assert profile.risk_level == RiskLevel.LOW

    # Step 3: Person leaves shelf area (+15) -> Total = 60 (SUSPICIOUS)
    p_state.active_shelf_id = None
    engine.process_person_movement(p_state, 1004.0)
    assert profile.risk_score == 60
    assert profile.risk_level == RiskLevel.SUSPICIOUS

    # Step 4: Person enters exit zone (+30) + no checkout (+30) -> Clamped to 100 (HIGH)
    p_state.current_zone_type = "EXIT_ZONE"
    engine.process_person_movement(p_state, 1010.0)
    assert profile.risk_score == 100
    assert profile.risk_level == RiskLevel.HIGH
    assert len(profile.timeline) >= 4

def test_risk_mitigation_on_checkout():
    cfg = TheftConfig()
    engine = RiskScoringEngine(cfg)
    profile = engine.get_or_create_profile(202)
    profile.add_timeline_event("Pickup", 20)
    profile.add_timeline_event("Missing", 25)
    assert profile.risk_score == 45

    # Shopper goes to checkout counter -> Risk mitigated (-50)
    p_state = PersonState(202, (900, 500), 1000.0)
    p_state.checkout_detected = True
    p_state.current_zone_type = "CHECKOUT_ZONE"
    engine.process_person_movement(p_state, 1005.0)
    assert profile.risk_score == 0
    assert profile.risk_level == RiskLevel.NORMAL

def test_theft_engine_demo_simulation(tmp_path):
    db_file = tmp_path / "test_theft.db"
    db = LocalDatabase(db_file)
    engine = TheftDetectionEngine(camera_id="camera_01", local_db=db)

    # Trigger demo simulation
    demo = engine.simulate_demo_event()
    assert demo is not None
    assert demo["person_id"] == 17
    assert demo["risk_score"] == 87
    assert demo["risk_level"] == "HIGH"
    assert demo["status"] == "ACTIVE"
    assert len(demo["timeline"]) >= 4

    # Verify SQLite persistence
    stored_events = db.get_theft_events(limit=10)
    assert len(stored_events) == 1
    assert stored_events[0]["event_id"] == demo["event_id"]
    assert stored_events[0]["risk_score"] == 87

    # Verify status update
    updated = engine.update_event_status(demo["event_id"], "RESOLVED")
    assert updated is True
    ev_after = db.get_theft_event_by_id(demo["event_id"])
    assert ev_after["status"] == "RESOLVED"

    metrics = db.get_theft_metrics()
    assert metrics["total_events"] == 1
    assert metrics["resolved_events"] == 1
    assert metrics["active_alerts"] == 0

def test_exit_without_billing_corridor_shelf_c():
    zm = StoreZoneManager(camera_id="camera_test")
    it = InteractionTracker(zm)
    re = RiskScoringEngine()
    t0 = 2000.0

    # Person #202 enters near Shelf C ([800, 40, 1240, 270])
    dets = [DummyDetection("person", (950, 100, 1050, 260), track_id=202)]
    persons = it.update(dets, timestamp=t0)
    assert 202 in persons
    assert persons[202].active_shelf_id == "SHELF_C"

    # Dwells at Shelf C for 2 seconds
    t1 = t0 + 2.5
    persons = it.update(dets, timestamp=t1)
    re.process_person_movement(persons[202], t1)
    p202 = re.get_or_create_profile(202)
    assert p202.flag_shelf_pickup is True

    # Person #202 walks directly into the exit corridor between Shelf C & Billing Counter (Y=310, X=1000)
    # WITHOUT ever visiting Checkout Zone
    t2 = t1 + 3.0
    exit_dets = [DummyDetection("person", (980, 280, 1060, 350), track_id=202)]
    persons = it.update(exit_dets, timestamp=t2)
    assert persons[202].checkout_detected is False
    assert persons[202].exit_detected is True

    re.process_person_movement(persons[202], t2)

    # Must immediately trigger HIGH RISK theft alert (>= 85)
    assert p202.risk_score >= 85
    assert p202.risk_level.value == "HIGH"
    assert any("without POS billing" in e.description for e in p202.timeline)
