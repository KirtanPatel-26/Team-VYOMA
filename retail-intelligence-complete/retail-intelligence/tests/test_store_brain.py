import pytest
from app.analytics.brain import RetailStoreBrain
from app.analytics.roi import BusinessImpactEngine
from app.analytics.copilot import RetailCopilot
from app.inventory.alerts import build_alerts


def test_retail_store_brain_predictions():
    brain = RetailStoreBrain()
    
    stock_items = [
        {
            "product_id": "SKU001",
            "product_name": "Coca Cola Can",
            "stock": 0,
            "minimum_stock": 2,
            "shelf_zone": "Shelf B",
            "price": 40.0,
            "status": "OUT_OF_STOCK"
        },
        {
            "product_id": "SKU002",
            "product_name": "Amul Milk 500ml",
            "stock": 1,
            "minimum_stock": 2,
            "shelf_zone": "Shelf C",
            "price": 32.0,
            "status": "LOW_STOCK"
        },
        {
            "product_id": "SKU003",
            "product_name": "Oreo Cookies",
            "stock": 8,
            "minimum_stock": 2,
            "shelf_zone": "Shelf A",
            "price": 30.0,
            "status": "IN_STOCK"
        }
    ]
    traffic_data = {"current_customers": 12, "total_in": 45}
    queue_data = {"queue_length": 4, "estimated_wait_time_min": 6.5, "congestion": True, "recommendation": "Open Counter 2"}
    shelf_audit = {
        "shelves": [
            {
                "shelf_code": "SHELF_A",
                "zone": "Shelf A (Snacks)",
                "status": "MISPLACED_ITEMS",
                "misplaced_items": ["Coca Cola Can"]
            }
        ]
    }

    result = brain.update(stock_items, traffic_data, queue_data, shelf_audit)

    assert "sku_predictions" in result
    assert "top_prioritized_actions" in result
    assert len(result["sku_predictions"]) == 3

    # Check depleted SKU001
    coke_pred = next(p for p in result["sku_predictions"] if p["sku_id"] == "SKU001")
    assert coke_pred["risk_level"] == "CRITICAL"
    assert "DEPLETED" in coke_pred["stockout_eta_formatted"]
    assert "Why?" in coke_pred["why_reasoning"] or "Stock reached zero" in coke_pred["why_reasoning"]
    assert coke_pred["revenue_at_risk"] > 0

    # Check low stock SKU002
    milk_pred = next(p for p in result["sku_predictions"] if p["sku_id"] == "SKU002")
    assert milk_pred["risk_level"] in ["CRITICAL", "HIGH"]
    assert milk_pred["sales_velocity_hourly"] > 0
    assert milk_pred["stockout_eta_minutes"] > 0

    # Check prioritized actions ordering
    actions = result["top_prioritized_actions"]
    assert len(actions) > 0
    # Highest priority actions should be at the top
    assert actions[0]["priority"] == 1


def test_business_impact_engine():
    roi = BusinessImpactEngine()
    
    stock_items = [
        {"product_id": "SKU001", "product_name": "Coca Cola", "stock": 0, "price": 40.0, "status": "OUT_OF_STOCK"},
        {"product_id": "SKU002", "product_name": "Milk", "stock": 5, "price": 30.0, "status": "IN_STOCK"}
    ]
    queue_data = {"queue_length": 5, "estimated_wait_time_min": 7.0, "congestion": True}
    traffic_data = {"current_customers": 10, "total_in": 30}

    impact = roi.update(stock_items, queue_data, traffic_data, time_delta_sec=10.0)

    assert impact["total_estimated_lost_sales_today"] > 0
    assert impact["lost_sales_stockout_today"] > 0
    assert impact["lost_sales_queue_today"] > 0
    assert impact["revenue_protected_today"] > 0
    assert impact["staff_hours_saved_today"] > 0
    assert impact["stockout_reduction_pct"] > 0


def test_alerts_with_brain_data():
    stock_items = [
        {"product_id": "SKU001", "product_name": "Coca Cola Can", "stock": 1, "minimum_stock": 2, "price": 40.0, "status": "LOW_STOCK"}
    ]
    queue_data = {"queue_length": 0, "congestion": False}
    brain_data = {
        "sku_predictions": [
            {
                "sku_id": "SKU001",
                "stockout_eta_formatted": "24 mins",
                "sales_velocity_hourly": 2.5,
                "revenue_at_risk": 160.0
            }
        ]
    }

    alerts = build_alerts(stock_items, queue_data, brain_data=brain_data)
    assert len(alerts) == 1
    assert "24 mins" in alerts[0]["message"]
    assert alerts[0]["revenue_at_risk"] == 160.0


def test_copilot_store_manager_queries():
    copilot = RetailCopilot()
    
    store_state = {
        "traffic": {"current_customers": 8, "current_staff": 2, "customer_to_staff_ratio": "4.0 : 1", "total_in": 50},
        "queue": {"queue_length": 3, "estimated_wait_time_min": 4.5, "congestion": False},
        "stock": {"items": [{"product_name": "Cadbury Dairy Milk", "product_id": "SKU004", "status": "LOW_STOCK", "stock": 1, "minimum_stock": 2}]},
        "brain": {
            "top_prioritized_actions": [
                {"priority": 1, "type": "RESTOCK", "target": "Cadbury Dairy Milk", "zone": "Shelf A", "action": "Refill Cadbury Dairy Milk within 20 mins", "deadline_mins": 20, "revenue_at_risk": 120.0}
            ],
            "sku_predictions": [
                {
                    "sku_id": "SKU004",
                    "product_name": "Cadbury Dairy Milk",
                    "risk_level": "HIGH",
                    "why_reasoning": "• Shelf buffer depleted to 1 unit.\n• Consumption velocity 2.1 units/hr.",
                    "stockout_eta_formatted": "28 mins",
                    "current_stock": 1,
                    "min_stock": 2,
                    "sales_velocity_hourly": 2.1,
                    "confidence_score": 92,
                    "revenue_at_risk": 120.0,
                    "recommended_action": "Refill Cadbury Dairy Milk within 20 minutes"
                }
            ]
        },
        "business_impact": {
            "lost_sales_stockout_today": 350.0,
            "lost_sales_queue_today": 180.0,
            "total_estimated_lost_sales_today": 530.0,
            "revenue_protected_today": 4200.0,
            "staff_hours_saved_today": 3.4,
            "stockout_reduction_pct": 34.0
        }
    }

    # Query 1: Tactical actions
    r1 = copilot.generate_response("What should I do right now?", store_state)
    assert "Directives" in r1["response"] or "Refill" in r1["response"]

    # Query 2: Explainable reasoning
    r2 = copilot.generate_response("Why is Dairy Milk urgent?", store_state)
    assert "Explainable AI Reasoning" in r2["response"]
    assert "Dairy Milk" in r2["response"]

    # Query 3: Business impact
    r3 = copilot.generate_response("What happened today? Show financial impact", store_state)
    assert "Revenue Protected" in r3["response"]
    assert "Estimated Lost Sales" in r3["response"]
