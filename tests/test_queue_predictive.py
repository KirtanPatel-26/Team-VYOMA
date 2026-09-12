import pytest
from app.analytics.queue import QueueAnalytics
from app.detection.results import Detection

def test_queue_predictive_forecasting():
    queue = QueueAnalytics(queue_zone=[800, 300, 1200, 700], threshold=4)

    # 1. Optimal conditions: 1 person
    p1 = [Detection(class_id=0, class_name="person", confidence=0.9, bbox=(850, 400, 900, 500), track_id=1)]
    res = queue.update(p1)
    assert res["queue_length"] == 1
    assert res["congestion"] is False
    assert "optimal" in res["recommendation"].lower()

    # 2. Predictive congestion: simulate traffic influx surge
    p2 = [
        Detection(class_id=0, class_name="person", confidence=0.9, bbox=(850, 400, 900, 500), track_id=1),
        Detection(class_id=0, class_name="person", confidence=0.9, bbox=(900, 400, 950, 500), track_id=2),
        Detection(class_id=0, class_name="person", confidence=0.9, bbox=(950, 400, 1000, 500), track_id=3)
    ]
    # Influx surge of +50%
    res_surge = queue.update(p2, store_traffic_influx=50.0)
    assert res_surge["queue_length"] == 3
    assert res_surge["predicted_queue_5min"] >= 4.0
    assert res_surge["predictive_congestion"] is True
    assert "PROACTIVE ALERT" in res_surge["recommendation"]

def test_queue_empirical_service_time():
    queue = QueueAnalytics(queue_zone=[800, 300, 1200, 700], threshold=3)

    # Person 1 enters
    p1 = [Detection(class_id=0, class_name="person", confidence=0.9, bbox=(850, 400, 900, 500), track_id=10)]
    queue.update(p1)
    assert 10 in queue.queue_entries

    # Person 1 departs (empty detections)
    res_empty = queue.update([])
    assert 10 not in queue.queue_entries
    assert "empirical_avg_service_sec" in res_empty
