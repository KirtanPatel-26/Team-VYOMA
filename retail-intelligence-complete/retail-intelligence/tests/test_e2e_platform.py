from app.analytics.traffic import TrafficAnalytics
from app.analytics.queue import QueueAnalytics
from app.analytics.shelf import ShelfAnalytics
from app.inventory.stock import StockAnalyzer
from app.inventory.alerts import build_alerts
from app.products.catalog import ProductCatalog
from app.database.local import LocalDatabase
from app.detection.results import Detection
from pathlib import Path
import tempfile

def test_traffic_analytics():
    traffic = TrafficAnalytics(zones=[{"name": "Beverages", "bbox": [0, 0, 200, 200]}])
    
    # Simulate person detection
    d1 = Detection(class_id=0, class_name="person", confidence=0.9, bbox=(50, 50, 100, 150), track_id=101)
    res = traffic.update([d1])
    
    assert res["current_people"] == 1
    assert res["total_in"] == 1
    assert "heatmap_grid" in res
    assert len(res["heatmap_grid"]) == 20

def test_queue_analytics():
    queue = QueueAnalytics(queue_zone=[800, 300, 1200, 700], threshold=3)
    
    # 3 persons in queue -> congestion
    persons = [
        Detection(class_id=0, class_name="person", confidence=0.9, bbox=(850, 400, 900, 500)),
        Detection(class_id=0, class_name="person", confidence=0.9, bbox=(920, 400, 970, 500)),
        Detection(class_id=0, class_name="person", confidence=0.9, bbox=(1000, 400, 1050, 500)),
    ]
    res = queue.update(persons)
    assert res["queue_length"] == 3
    assert res["congestion"] is True
    assert "recommend" in res["recommendation"].lower()

def test_stock_and_alerts():
    catalog_path = Path("data/products.json")
    catalog = ProductCatalog(catalog_path)
    stock_analyzer = StockAnalyzer(catalog)
    
    # 0 Fanta Orange detected -> OUT_OF_STOCK
    counts = {"Pringles Original": 4, "Oreo": 3}
    stock_rep = stock_analyzer.analyze(counts)
    
    fanta_item = next(i for i in stock_rep["items"] if i["product_name"] == "Fanta Orange")
    assert fanta_item["status"] == "OUT_OF_STOCK"
    
    queue_data = {"congestion": True, "queue_length": 4, "estimated_wait_time_min": 3.0, "recommendation": "Open Counter 2"}
    alerts = build_alerts(stock_rep["items"], queue_data)
    
    assert any(a["type"] == "OUT_OF_STOCK" for a in alerts)
    assert any(a["type"] == "QUEUE_CONGESTION" for a in alerts)

def test_local_database_resilience():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_retail.db"
        db = LocalDatabase(db_path)
        
        # Log snapshot
        db.log_snapshot(
            traffic_data={"total_in": 10, "total_out": 5, "current_people": 5, "avg_dwell_time": 42.0},
            queue_data={"queue_length": 3, "estimated_wait_time_sec": 90.0, "congestion": False},
            alerts_list=[{"id": "alert_1", "type": "LOW_STOCK", "severity": "warning", "title": "Low Stock", "message": "Refill Fanta", "zone": "Beverages"}]
        )
        
        history = db.get_recent_history(limit=5)
        assert len(history["traffic"]) == 1
        assert len(history["queue"]) == 1
        assert len(history["alerts"]) == 1
