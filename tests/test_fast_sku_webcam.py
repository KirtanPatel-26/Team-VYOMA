import sys
import time
from pathlib import Path
import cv2
import numpy as np

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app.detection.detector import ObjectDetector
from inference.product_detector import ProductDetector

def test_product_detector_loads_best_pt():
    weights_path = ROOT_DIR / "models" / "trained" / "best.pt"
    if not weights_path.exists():
        print(f"[SKIP] {weights_path} not found yet.")
        return

    detector = ProductDetector(
        model_path=str(weights_path),
        config_path=str(ROOT_DIR / "configs" / "products.yaml"),
        confidence_threshold=0.50
    )
    assert detector is not None
    assert len(detector.expected_names) == 10
    print("[OK] ProductDetector successfully initialized with custom trained checkpoint!")

def test_webcam_dual_speed_integration():
    detector = ObjectDetector()
    # Switch to webcam mode (device 0)
    detector.set_active_source(0)
    assert detector.is_webcam is True
    assert detector.mode == "OWLV2_WEBCAM"
    assert detector.owlv2_detector is not None

    # Test synthetic frame detection
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    t0 = time.time()
    dets = detector.detect(frame)
    latency_ms = (time.time() - t0) * 1000
    print(f"[OK] Webcam frame processed in {latency_ms:.1f}ms. Total detections: {len(dets)}")
    assert isinstance(dets, list)

    if detector.owlv2_detector is not None:
        detector.owlv2_detector.stop_worker()

def test_colgate_and_dove_user_images():
    weights_path = ROOT_DIR / "models" / "trained" / "best.pt"
    if not weights_path.exists():
        print(f"[SKIP] {weights_path} not found yet.")
        return

    detector = ObjectDetector()
    detector.set_active_source(0) # Webcam mode

    colgate_path = r"C:\Users\kirtan patel\.gemini\antigravity\brain\b0e944d2-a089-440e-80f7-a26962e2fcc6\.user_uploaded\media_1789202613498.jpg"
    dove_path = r"C:\Users\kirtan patel\.gemini\antigravity\brain\b0e944d2-a089-440e-80f7-a26962e2fcc6\.user_uploaded\media_1789202618794.jpg"

    # 1. Test Colgate image
    img_colgate = cv2.imread(colgate_path)
    assert img_colgate is not None
    dets_colgate = detector.detect(img_colgate)
    print(f"[Test] Colgate image detections: {[d.product_name for d in dets_colgate]}")

    # 2. Test Dove image
    img_dove = cv2.imread(dove_path)
    assert img_dove is not None
    dets_dove = detector.detect(img_dove)
    print(f"[Test] Dove image detections: {[d.product_name for d in dets_dove]}")

    if detector.owlv2_detector is not None:
        detector.owlv2_detector.stop_worker()

    print("[OK] User image detection tests completed successfully!")

if __name__ == "__main__":
    test_product_detector_loads_best_pt()
    test_webcam_dual_speed_integration()
    test_colgate_and_dove_user_images()
