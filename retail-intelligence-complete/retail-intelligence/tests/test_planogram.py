import pytest
from app.analytics.planogram import PlanogramAuditor
from app.detection.results import Detection

def test_planogram_auditor_compliance_and_violations():
    zones_config = [
        {
            "name": "Beverages & Juices",
            "shelf_code": "SHELF_B",
            "bbox": [40, 330, 520, 580],
            "slots": [
                {"position": 1, "bbox": [40, 330, 200, 580], "expected_sku": "SKU001", "expected_name": "Fanta Orange"},
                {"position": 2, "bbox": [200, 330, 360, 580], "expected_sku": "SKU005", "expected_name": "Real Orange Juice"},
                {"position": 3, "bbox": [360, 330, 520, 580], "expected_sku": "SKU007", "expected_name": "Coca Cola"}
            ]
        }
    ]
    
    auditor = PlanogramAuditor({"zones": zones_config})
    
    # Slot 1: Compliant (Fanta at x=100, y=450)
    d1 = Detection(
        class_id=1, class_name="bottle", confidence=0.92,
        bbox=(80, 400, 140, 500), product_name="Fanta Orange", sku_id="SKU001"
    )
    # Slot 2: Misplaced (Coca Cola placed in Position 2 where Real Orange Juice is expected!)
    d2 = Detection(
        class_id=1, class_name="bottle", confidence=0.88,
        bbox=(240, 400, 300, 500), product_name="Coca Cola", sku_id="SKU007"
    )
    # Slot 3: Empty (No detection in slot 3)
    
    res = auditor.audit([d1, d2], zones=zones_config)
    
    assert res["total_slots"] == 3
    assert res["compliant_slots"] == 1
    assert res["misplaced_slots"] == 1
    assert res["empty_slots"] == 1
    assert round(res["overall_compliance_score"], 1) == 33.3
    
    # Check violation messages
    violations = res["violations"]
    assert len(violations) == 2
    
    misplaced_v = next(v for v in violations if v["status"] == "MISPLACED")
    assert misplaced_v["position"] == 2
    assert "Real Orange Juice" in misplaced_v["message"]
    assert "Coca Cola" in misplaced_v["message"]
    
    empty_v = next(v for v in violations if v["status"] == "EMPTY")
    assert empty_v["position"] == 3
