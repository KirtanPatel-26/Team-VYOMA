import pytest
import numpy as np
from pathlib import Path
from unittest.mock import MagicMock, patch

from inference.product_detector import ProductDetector, IncompatibleModelError
from app.detection.detector import ObjectDetector
from app.detection.results import Detection

def test_product_detector_rejects_incompatible_coco_model():
    """
    Test that ProductDetector strictly refuses to load a generic 80-class COCO checkpoint.
    This guarantees prevention of the anti-pattern where generic COCO 'bottle' was mapped to 'Fanta Orange'.
    """
    with patch("inference.product_detector.EdgeYOLODetector") as mock_edge_yolo:
        mock_instance = MagicMock()
        # Simulate COCO 80-class model
        mock_instance.class_names = {i: f"coco_class_{i}" for i in range(80)}
        mock_edge_yolo.return_value = mock_instance

        with pytest.raises(IncompatibleModelError) as exc_info:
            ProductDetector(
                model_path="models/yolo11n.pt",
                config_path="configs/products.yaml"
            )

        assert "Checkpoint Rejected" in str(exc_info.value)
        assert "80 classes" in str(exc_info.value)

def test_product_detector_dual_confidence_thresholds():
    """
    Test that:
    - Predictions >= confidence_threshold (0.75) receive full SKU ID and product name.
    - Predictions between 0.25 and 0.75 receive 'Unknown / Low Confidence' with sku_id=None.
    - All predictions carry source='trained_sku_model'.
    """
    with patch("inference.product_detector.EdgeYOLODetector") as mock_edge_yolo:
        mock_instance = MagicMock()
        # Simulate valid 10-SKU model
        mock_instance.class_names = {
            0: "Fanta Orange",
            1: "Pringles Original",
            2: "Oreo",
            3: "Amul Taaza",
            4: "Real Orange Juice",
            5: "Dove Soap",
            6: "Coca Cola",
            7: "Lays Classic",
            8: "Dairy Milk",
            9: "Colgate Paste"
        }

        # Mock predictions: 1 high-confidence box (0.88), 1 low-confidence box (0.42)
        box_high = MagicMock()
        box_high.conf = [0.88]
        box_high.cls = [0] # Fanta Orange
        box_high.xyxy = [[10, 20, 50, 90]]

        box_low = MagicMock()
        box_low.conf = [0.42]
        box_low.cls = [1] # Pringles Original
        box_low.xyxy = [[100, 120, 160, 200]]

        mock_result = MagicMock()
        mock_result.boxes = [box_high, box_low]
        mock_instance.predict_frame.return_value = [mock_result]
        mock_edge_yolo.return_value = mock_instance

        detector = ProductDetector(
            model_path="models/trained/mock_best.pt",
            config_path="configs/products.yaml",
            confidence_threshold=0.75,
            detection_floor=0.25
        )

        dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        detections = detector.detect(dummy_frame)

        assert len(detections) == 2

        # Verify high confidence detection
        d_high = detections[0]
        assert d_high.product_name == "Fanta Orange"
        assert d_high.sku_id == "SKU001"
        assert d_high.confidence == 0.88
        assert d_high.source == "trained_sku_model"

        # Verify low confidence detection
        d_low = detections[1]
        assert d_low.product_name == "Unknown / Low Confidence"
        assert d_low.sku_id is None
        assert d_low.confidence == 0.42
        assert d_low.source == "trained_sku_model"

def test_object_detector_fallback_mode():
    """
    Test that ObjectDetector correctly detects when trained model is absent
    and falls back cleanly to DEMO_SIMULATION mode.
    """
    detector = ObjectDetector(
        model_path="models/yolo11n.pt",
        product_model_path="models/trained/non_existent_best.pt"
    )

    assert detector.mode == "DEMO_SIMULATION"
    assert detector.demo_simulator is not None

    dummy_frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    detections = detector.detect(dummy_frame)
    # Empty frame should produce 0 detections
    assert isinstance(detections, list)
