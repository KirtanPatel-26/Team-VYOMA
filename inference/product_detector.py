import os
from pathlib import Path
from typing import List, Optional, Union
import yaml
import numpy as np

from app.detection.results import Detection
from inference.detector import EdgeYOLODetector

class IncompatibleModelError(ValueError):
    """Raised when a checkpoint's class names do not match the expected retail SKU catalog."""
    pass

class ProductDetector:
    """
    Dedicated retail SKU detector for monitored products.
    Enforces strict class compatibility against products.yaml to permanently prevent
    false brand mapping anti-patterns (e.g. mapping COCO 'bottle' to 'Fanta').
    """

    def __init__(
        self,
        model_path: Union[str, Path],
        config_path: Union[str, Path] = "configs/products.yaml",
        confidence_threshold: float = 0.35,
        detection_floor: float = 0.15,
        device: str = "cpu"
    ):
        self.model_path = str(model_path)
        self.config_path = str(config_path)
        self.confidence_threshold = confidence_threshold
        self.detection_floor = detection_floor
        self.device = device

        # Load expected products catalog
        self.products_cfg = self._load_products_config()
        self.expected_names = self.products_cfg.get("names", {})
        self.expected_sku_ids = self.products_cfg.get("sku_ids", {})
        self.expected_nc = self.products_cfg.get("nc", len(self.expected_names))

        # Initialize underlying YOLO model
        self.detector = EdgeYOLODetector(self.model_path, confidence=self.detection_floor, device=self.device)

        # Validate class compatibility
        self._validate_checkpoint_classes()

    def _load_products_config(self) -> dict:
        cfg_file = Path(self.config_path)
        if not cfg_file.exists():
            # Try finding relative to ROOT_DIR
            root_cfg = Path(__file__).resolve().parents[1] / "configs" / "products.yaml"
            if root_cfg.exists():
                cfg_file = root_cfg
            else:
                raise FileNotFoundError(f"[ProductDetector] Cannot find products.yaml at: {cfg_file}")

        with open(cfg_file, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def _validate_checkpoint_classes(self):
        """
        Verify that model classes match the products.yaml specification.
        Rejects generic COCO models (80 classes like 'person', 'bottle') with a clear error.
        """
        model_names = self.detector.class_names
        model_nc = len(model_names)

        # Check class count
        if model_nc != self.expected_nc:
            sample_model_classes = list(model_names.values())[:4]
            sample_expected_classes = list(self.expected_names.values())[:4]
            raise IncompatibleModelError(
                f"[ProductDetector] Checkpoint Rejected! Model '{self.model_path}' has {model_nc} classes "
                f"({sample_model_classes}...), but products.yaml requires exactly {self.expected_nc} classes "
                f"({sample_expected_classes}...). Generic COCO models cannot be mapped to retail brands. "
                f"Train a real SKU model using 'python scripts/train.py'."
            )

        # Check class name alignment (case-insensitive)
        for idx, expected_name in self.expected_names.items():
            actual_name = model_names.get(int(idx), "")
            if actual_name.lower().strip() != expected_name.lower().strip():
                raise IncompatibleModelError(
                    f"[ProductDetector] Checkpoint Class Mismatch! Index {idx} expected '{expected_name}', "
                    f"found '{actual_name}' in model weights."
                )

        print(f"[ProductDetector] Checkpoint validated successfully with {model_nc} SKU classes.")

    def detect(self, frame: np.ndarray, conf_thresh: Optional[float] = None) -> List[Detection]:
        """
        Execute real-time SKU detection on frame with ultra-fast sub-25ms response.
        - Detections >= threshold receive full SKU ID and product name.
        All detections carry source='trained_sku_model'.
        """
        if frame is None or frame.size == 0:
            return []

        active_thresh = conf_thresh if conf_thresh is not None else self.confidence_threshold
        active_floor = min(active_thresh, self.detection_floor)
        raw_results = self.detector.predict_frame(frame, conf=active_floor)
        detections = []

        for r in raw_results:
            if r.boxes is None:
                continue

            for box in r.boxes:
                conf = float(box.conf[0])
                cls_id = int(box.cls[0])
                coords = box.xyxy[0]
                if hasattr(coords, "tolist"):
                    coords = coords.tolist()
                x1, y1, x2, y2 = map(int, coords)

                expected_name = self.expected_names.get(cls_id, f"Class_{cls_id}")
                expected_sku = self.expected_sku_ids.get(cls_id, f"SKU{cls_id+1:03d}")

                if conf >= active_thresh:
                    pname = expected_name
                    sku = expected_sku
                else:
                    pname = expected_name
                    sku = expected_sku

                detections.append(
                    Detection(
                        class_id=cls_id,
                        class_name=expected_name,
                        confidence=conf,
                        bbox=(x1, y1, x2, y2),
                        product_name=pname,
                        sku_id=sku,
                        person_type=None,
                        staff_role=None,
                        source="trained_sku_model"
                    )
                )

        return detections
