def test_imports():
    from app.detection.detector import ObjectDetector
    from app.detection.tracker import CentroidTracker
    assert ObjectDetector
    assert CentroidTracker
