import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
import numpy as np
from app.detection.detector import ObjectDetector

def test_source_isolation_demo_vs_upload_vs_webcam():
    detector = ObjectDetector()

    # 1. Synthetic Demo Video (MUST remain DEMO_SIMULATION / TRAINED_MODEL and not webcam)
    detector.set_active_source("videos/store.mp4")
    assert detector.mode in ["DEMO_SIMULATION", "TRAINED_MODEL"]
    assert detector.is_synthetic_demo is True
    assert detector.is_webcam is False

    # 2. Uploaded Video file (REAL_EDGE_CV or TRAINED_MODEL, not webcam)
    detector.set_active_source("videos/uploaded_aisle.mp4")
    assert detector.mode in ["REAL_EDGE_CV", "TRAINED_MODEL"]
    assert detector.is_synthetic_demo is False
    assert detector.is_webcam is False

    # 3. Internal PC Webcam (Device 0)
    detector.set_active_source(0)
    assert detector.mode == "OWLV2_WEBCAM"
    assert detector.is_synthetic_demo is False
    assert detector.is_webcam is True

    # 4. External USB Webcam (Device 1)
    detector.set_active_source(1)
    assert detector.mode == "OWLV2_WEBCAM"
    assert detector.is_synthetic_demo is False
    assert detector.is_webcam is True

    # 5. External USB Webcam as numeric string ("2")
    detector.set_active_source("2")
    assert detector.mode == "OWLV2_WEBCAM"
    assert detector.is_synthetic_demo is False
    assert detector.is_webcam is True

    # 6. Switch back to Demo Video (Workers clean up, mode reverts)
    detector.set_active_source("videos/store.mp4")
    assert detector.mode in ["DEMO_SIMULATION", "TRAINED_MODEL"]
    assert detector.is_synthetic_demo is True
    assert detector.is_webcam is False
    print("\n[OK] All source routing tests passed! Webcam triggers OWLv2 while Demo & Uploaded videos remain on YOLO11n.")

def test_mock_frame_detection_safety():
    detector = ObjectDetector()
    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    # Demo video detection test
    detector.set_active_source("videos/store.mp4")
    dets_demo = detector.detect(frame)
    assert isinstance(dets_demo, list)

    # Webcam detection test (runs safely even if OWLv2 worker is still starting)
    detector.set_active_source(0)
    dets_cam = detector.detect(frame)
    assert isinstance(dets_cam, list)

    if detector.owlv2_detector is not None:
        detector.owlv2_detector.stop_worker()
    print("[OK] Frame detection safety test passed!")

def test_colgate_and_dove_sku_prompts_and_threshold():
    from app.detection.owlv2_detector import Owlv2SKUDetector, RETAIL_SKU_PROMPTS
    
    detector = Owlv2SKUDetector(confidence_threshold=0.13)
    assert detector.confidence_threshold <= 0.15, "Threshold must be calibrated for sensitive webcam zero-shot detection"

    # Find SKU metadata for Dove Soap and Colgate Paste
    dove_meta = next((s for s in RETAIL_SKU_PROMPTS if s["sku_id"] == "SKU006"), None)
    colgate_meta = next((s for s in RETAIL_SKU_PROMPTS if s["sku_id"] == "SKU010"), None)

    assert dove_meta is not None
    assert colgate_meta is not None
    assert dove_meta["name"] == "Dove Soap"
    assert colgate_meta["name"] == "Colgate Paste"

    # Verify comprehensive prompt variations cover boxes, bars, tubes, and brand names
    dove_prompts = [p.lower() for p in dove_meta["prompts"]]
    assert any("soap bar" in p or "bar of soap" in p for p in dove_prompts)
    assert any("dove" in p for p in dove_prompts)

    colgate_prompts = [p.lower() for p in colgate_meta["prompts"]]
    assert any("tube" in p for p in colgate_prompts)
    assert any("toothpaste" in p for p in colgate_prompts)
    assert any("colgate" in p for p in colgate_prompts)

    # Verify prompt_to_sku maps all queries accurately
    for prompt_idx, meta in detector.prompt_to_sku.items():
        if meta["sku_id"] == "SKU006":
            assert meta["name"] == "Dove Soap"
        elif meta["sku_id"] == "SKU010":
            assert meta["name"] == "Colgate Paste"
    print("[OK] Colgate and Dove SKU prompt mappings verified!")

if __name__ == "__main__":
    test_source_isolation_demo_vs_upload_vs_webcam()
    test_mock_frame_detection_safety()
    test_colgate_and_dove_sku_prompts_and_threshold()
