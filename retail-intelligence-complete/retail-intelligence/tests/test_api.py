from fastapi.testclient import TestClient
import io
import cv2
import numpy as np
from app.main import app

def test_health():
    client = TestClient(app)
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_status_endpoint_reports_honest_mode():
    client = TestClient(app)
    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    # Detection mode can be TRAINED_MODEL, DEMO_SIMULATION, REAL_EDGE_CV, or OWLV2_WEBCAM
    assert data["detection_mode"] in ["TRAINED_MODEL", "DEMO_SIMULATION", "REAL_EDGE_CV", "OWLV2_WEBCAM"]
    assert "product_model_path" in data
    assert "confidence_threshold" in data

def test_detections_endpoint():
    client = TestClient(app)
    response = client.get("/api/detections")
    assert response.status_code == 200
    data = response.json()
    assert "detection_mode" in data
    assert "detections" in data

def test_ai_detect_image_upload():
    client = TestClient(app)
    # Generate a dummy test image in memory
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    ok, buf = cv2.imencode(".jpg", img)
    assert ok

    files = {"file": ("test_shelf.jpg", io.BytesIO(buf.tobytes()), "image/jpeg")}
    response = client.post("/api/ai/detect", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "detection_mode" in data
    assert "detections" in data

def test_brain_recommendations_endpoint():
    client = TestClient(app)
    response = client.get("/api/brain/recommendations")
    assert response.status_code == 200
    data = response.json()
    assert "sku_predictions" in data
    assert "top_prioritized_actions" in data

def test_business_impact_endpoint():
    client = TestClient(app)
    response = client.get("/api/business/impact")
    assert response.status_code == 200
    data = response.json()
    assert "total_estimated_lost_sales_today" in data
    assert "revenue_protected_today" in data
    assert "staff_hours_saved_today" in data

def test_system_integrity_endpoint():
    client = TestClient(app)
    response = client.get("/api/integrity")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "AUTHENTIC_EDGE_PIPELINE"
    assert "components" in data
    assert len(data["components"]) >= 6

def test_camera_sources_endpoint():
    client = TestClient(app)
    response = client.get("/api/camera/sources")
    assert response.status_code == 200
    data = response.json()
    assert "active_source" in data
    assert "is_webcam" in data
    assert "uploaded_videos" in data
    assert "demo_available" in data

def test_camera_switch_endpoint():
    client = TestClient(app)
    # Switch to demo store video
    response = client.post("/api/camera/switch", json={"source": "videos/store.mp4"})
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "store.mp4" in data["source"]

    # Switch to webcam 0 (even if physical hardware absent, should handle gracefully without crash)
    response2 = client.post("/api/camera/switch", json={"source": 0})
    assert response2.status_code == 200
    data2 = response2.json()
    assert "is_webcam" in data2
    assert data2["is_webcam"] is True

    # Revert to demo store
    client.post("/api/camera/switch", json={"source": "videos/store.mp4"})

def test_camera_upload_video_endpoint():
    client = TestClient(app)
    # Create a small dummy video payload
    dummy_video_bytes = b"\x00\x00\x00 ftypmp42\x00\x00\x00\x00isommp42\x00\x00\x00\x08free"
    files = {"file": ("test_store_clip.mp4", io.BytesIO(dummy_video_bytes), "video/mp4")}
    response = client.post("/api/camera/upload-video", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["filename"] == "test_store_clip.mp4"
    assert "path" in data

    # Revert back to standard demo
    client.post("/api/camera/switch", json={"source": "videos/store.mp4"})

