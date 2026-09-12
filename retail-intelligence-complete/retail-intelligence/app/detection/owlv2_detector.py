"""
SmartRetail AI - OWLv2 Zero-Shot Retail SKU Detector
=====================================================
Uses Google OWLv2 (google/owlv2-base-patch16-ensemble) for genuine open-vocabulary
zero-shot retail object detection on live webcams (both integrated PC webcams and
external USB webcams).

Runs on an asynchronous background thread to guarantee smooth 30 FPS camera
rendering on CPU-only hardware without pipeline starvation or lag.
"""

import os
import time
import threading
from typing import List, Tuple, Optional, Dict, Any
import cv2
import numpy as np
from PIL import Image

from app.detection.results import Detection


# 10 Monitored Retail SKUs with open-vocabulary vision-language queries
RETAIL_SKU_PROMPTS = [
    {
        "sku_id": "SKU001",
        "name": "Fanta Orange",
        "category": "Beverages",
        "prompts": ["a bottle of Fanta orange", "Fanta bottle", "a bottle of Fanta", "orange bottle of Fanta", "Fanta can", "Fanta drink"]
    },
    {
        "sku_id": "SKU002",
        "name": "Pringles Original",
        "category": "Chips",
        "prompts": ["a can of Pringles potato chips", "Pringles can", "Pringles container", "can of Pringles", "Pringles chips"]
    },
    {
        "sku_id": "SKU003",
        "name": "Oreo",
        "category": "Biscuits",
        "prompts": ["an Oreo cookie packet", "Oreo biscuit pack", "Oreo cookies packet", "Oreo biscuits", "packet of Oreos"]
    },
    {
        "sku_id": "SKU004",
        "name": "Amul Taaza",
        "category": "Milk",
        "prompts": ["an Amul milk packet", "Amul milk pouch", "Amul Taaza packet", "milk pouch", "Amul milk"]
    },
    {
        "sku_id": "SKU005",
        "name": "Real Orange Juice",
        "category": "Juices",
        "prompts": ["a carton of Real fruit juice", "Real orange juice carton", "Real fruit juice pack", "orange juice carton", "Real juice"]
    },
    {
        "sku_id": "SKU006",
        "name": "Dove Soap",
        "category": "Soap",
        "prompts": [
            "Dove soap",
            "a bar of Dove soap",
            "Dove soap bar",
            "Dove beauty bar",
            "Dove white beauty bar",
            "white soap bar",
            "a white bar of soap",
            "white bar of soap",
            "Dove soap box",
            "a Dove soap box",
            "box of Dove soap",
            "white soap box",
            "Dove cream bar",
            "Dove white soap",
            "bar of soap",
            "soap bar",
            "a bar of soap",
            "white soap",
            "soap"
        ]
    },
    {
        "sku_id": "SKU007",
        "name": "Coca Cola",
        "category": "Beverages",
        "prompts": ["a bottle of Coca Cola", "Coca Cola can", "Coke bottle", "Coca-Cola bottle", "can of Coke", "Coca Cola", "Coke"]
    },
    {
        "sku_id": "SKU008",
        "name": "Lays Classic",
        "category": "Chips",
        "prompts": ["a yellow packet of Lays potato chips", "Lays chips packet", "Lays classic potato chips", "yellow Lays packet", "packet of Lays chips"]
    },
    {
        "sku_id": "SKU009",
        "name": "Dairy Milk",
        "category": "Chocolates",
        "prompts": ["a Cadbury Dairy Milk chocolate bar", "Dairy Milk chocolate bar", "Dairy Milk chocolate", "Cadbury Dairy Milk", "Dairy Milk bar"]
    },
    {
        "sku_id": "SKU010",
        "name": "Colgate Paste",
        "category": "Personal Care",
        "prompts": [
            "Colgate toothpaste",
            "Colgate toothpaste tube",
            "a tube of Colgate toothpaste",
            "tube of Colgate toothpaste",
            "Colgate toothpaste box",
            "a Colgate toothpaste box",
            "toothpaste tube",
            "a tube of toothpaste",
            "toothpaste",
            "Colgate Dental Cream",
            "Colgate MaxFresh",
            "Colgate tube"
        ]
    }
]


class Owlv2SKUDetector:
    """
    Asynchronous OWLv2 Zero-Shot Object Detector for Live Webcams.
    """

    def __init__(
        self,
        model_name: str = "google/owlv2-base-patch16-ensemble",
        confidence_threshold: float = 0.09,
        target_size: Tuple[int, int] = (640, 640)
    ):
        self.model_name = model_name
        self.confidence_threshold = confidence_threshold
        self.target_size = target_size

        self.processor = None
        self.model = None
        self.is_loaded = False
        self.is_loading = False
        self.device = "cpu"

        # Build flat list of query prompts and lookup map to SKU metadata
        self.query_texts = []
        self.prompt_to_sku: Dict[int, Dict[str, Any]] = {}

        idx = 0
        for class_idx, sku in enumerate(RETAIL_SKU_PROMPTS):
            for prompt in sku["prompts"]:
                self.query_texts.append(prompt)
                self.prompt_to_sku[idx] = {
                    "class_id": class_idx,
                    "sku_id": sku["sku_id"],
                    "name": sku["name"],
                    "category": sku["category"],
                    "prompt": prompt
                }
                idx += 1

        # Asynchronous worker state
        self._lock = threading.Lock()
        self._latest_frame: Optional[np.ndarray] = None
        self._cached_detections: List[Detection] = []
        self._last_inference_time: float = 0.0
        self._worker_running = False
        self._worker_thread: Optional[threading.Thread] = None

    def start_worker(self):
        """Starts the background inference thread if not already running."""
        if self._worker_running:
            return

        self._worker_running = True
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()
        print("[OWLv2] Asynchronous zero-shot SKU worker started for live webcam.")

    def stop_worker(self):
        """Stops the background inference thread."""
        self._worker_running = False
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=1.0)
        self._worker_thread = None

    def load_model(self):
        """Loads OWLv2 model and processor into memory (lazy loaded)."""
        if self.is_loaded or self.is_loading:
            return

        self.is_loading = True
        try:
            import torch
            from transformers import Owlv2Processor, Owlv2ForObjectDetection

            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            print(f"[OWLv2] Loading zero-shot model '{self.model_name}' on device '{self.device}'...")

            self.processor = Owlv2Processor.from_pretrained(self.model_name)
            self.model = Owlv2ForObjectDetection.from_pretrained(self.model_name)
            self.model.to(self.device)
            self.model.eval()

            self.is_loaded = True
            print(f"[OWLv2] [OK] Model successfully loaded and ready for zero-shot retail detection!")
        except Exception as e:
            print(f"[OWLv2] [ERROR] Failed loading OWLv2 model: {e}")
            self.is_loaded = False
        finally:
            self.is_loading = False

    def update_frame(self, frame: np.ndarray):
        """Submits a new frame from the webcam stream for processing."""
        if frame is None or frame.size == 0:
            return

        with self._lock:
            # Keep latest frame for background processing
            self._latest_frame = frame.copy()

    def get_detections(self) -> List[Detection]:
        """Returns the most recent zero-shot detections computed by OWLv2."""
        with self._lock:
            return list(self._cached_detections)

    def _worker_loop(self):
        """Background loop continuously processing the latest webcam frame."""
        # Ensure model is loaded in the worker thread
        if not self.is_loaded:
            self.load_model()

        while self._worker_running:
            frame_to_process = None
            with self._lock:
                if self._latest_frame is not None:
                    frame_to_process = self._latest_frame
                    self._latest_frame = None

            if frame_to_process is None or not self.is_loaded:
                time.sleep(0.05)
                continue

            try:
                # Run zero-shot inference
                t0 = time.time()
                dets = self._run_inference(frame_to_process)
                inference_duration = time.time() - t0

                with self._lock:
                    self._cached_detections = dets
                    self._last_inference_time = time.time()

                # Yield briefly to CPU
                time.sleep(0.05)
            except Exception as e:
                print(f"[OWLv2] Error during background inference: {e}")
                time.sleep(0.5)

    def _run_inference(self, frame: np.ndarray) -> List[Detection]:
        """Executes OWLv2 zero-shot detection on a single frame."""
        if not self.is_loaded or self.model is None or self.processor is None:
            return []

        import torch

        orig_h, orig_w, _ = frame.shape
        # Convert BGR to RGB PIL image
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(rgb)

        # Batch inputs
        inputs = self.processor(
            text=[self.query_texts],
            images=pil_image,
            return_tensors="pt"
        )
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = self.model(**inputs)

        # Post-process bounding boxes with backward/forward compatible dispatch
        target_sizes = torch.tensor([[orig_h, orig_w]], device=self.device)
        if hasattr(self.processor, "post_process_grounded_object_detection"):
            results = self.processor.post_process_grounded_object_detection(
                outputs=outputs,
                target_sizes=target_sizes,
                threshold=self.confidence_threshold
            )
        elif hasattr(self.processor, "post_process_object_detection"):
            results = self.processor.post_process_object_detection(
                outputs=outputs,
                target_sizes=target_sizes,
                threshold=self.confidence_threshold
            )
        else:
            results = self.processor.image_processor.post_process_object_detection(
                outputs=outputs,
                target_sizes=target_sizes,
                threshold=self.confidence_threshold
            )

        detections: List[Detection] = []
        if not results:
            return detections

        r = results[0]
        boxes = r["boxes"].cpu().numpy()
        scores = r["scores"].cpu().numpy()
        labels = r["labels"].cpu().numpy()

        # Non-Maximum Suppression / De-duplication across query variations
        candidates = []
        for box, score, label_idx in zip(boxes, scores, labels):
            meta = self.prompt_to_sku.get(int(label_idx))
            if meta is None:
                continue

            x1, y1, x2, y2 = map(int, box)
            x1 = max(0, min(orig_w - 1, x1))
            y1 = max(0, min(orig_h - 1, y1))
            x2 = max(0, min(orig_w, x2))
            y2 = max(0, min(orig_h, y2))

            bw = x2 - x1
            bh = y2 - y1
            # Minimum box size threshold for retail items
            if bw < 25 or bh < 25:
                continue

            candidates.append({
                "meta": meta,
                "score": float(score),
                "bbox": (x1, y1, x2, y2),
                "area": bw * bh
            })

        # Sort candidates: for each SKU, prefer larger encompassing bounding boxes, then higher confidence
        candidates.sort(key=lambda c: (c["meta"]["sku_id"], -c["area"], -c["score"]))
        selected = []
        for cand in candidates:
            cand_box = cand["bbox"]
            overlap = False
            for sel in selected:
                sel_box = sel["bbox"]
                # Compute intersection
                ix1 = max(cand_box[0], sel_box[0])
                iy1 = max(cand_box[1], sel_box[1])
                ix2 = min(cand_box[2], sel_box[2])
                iy2 = min(cand_box[3], sel_box[3])
                if ix2 > ix1 and iy2 > iy1:
                    inter = (ix2 - ix1) * (iy2 - iy1)
                    union = cand["area"] + sel["area"] - inter
                    iou = inter / max(1, union)
                    min_area = min(cand["area"], sel["area"])
                    containment = inter / max(1, min_area)

                    same_sku = (cand["meta"]["sku_id"] == sel["meta"]["sku_id"])
                    if same_sku:
                        # Aggressive suppression for same SKU: eliminates nested boxes (e.g. logo inside tube)
                        if iou > 0.18 or containment > 0.30:
                            overlap = True
                            break
                    else:
                        # Cross-SKU suppression
                        if iou > 0.35 or containment > 0.55:
                            overlap = True
                            break
            if not overlap:
                selected.append(cand)

        # Convert to Detection objects
        for s in selected:
            meta = s["meta"]
            detections.append(
                Detection(
                    class_id=meta["class_id"],
                    class_name=meta["name"],
                    confidence=round(s["score"], 2),
                    bbox=s["bbox"],
                    product_name=meta["name"],
                    sku_id=meta["sku_id"],
                    source="owlv2_zero_shot"
                )
            )

        return detections
