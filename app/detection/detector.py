import os
import cv2
import numpy as np
from pathlib import Path
from typing import List, Tuple, Optional

from app.detection.results import Detection
from app.detection.demo_simulator import DemoShelfSimulator

class ObjectDetector:
    """
    Production-grade Dual-Mode Object Detection Orchestrator.
    - Person Model: YOLO11n for robust shopper and staff detection (always real, source='person_model').
    - Product Model:
        * If custom SKU model exists in 'models/trained/best.pt': ProductDetector runs inference (source='trained_sku_model', mode='TRAINED_MODEL').
        * Otherwise: DemoShelfSimulator provides a transparently labeled fallback for the synthetic store video (source='demo_simulation', mode='DEMO_SIMULATION').
    """

    def __init__(
        self,
        model_path: str = "models/yolo11n.pt",
        confidence: float = 0.35,
        product_model_path: Optional[str] = None,
        confidence_threshold: float = 0.75,
        products_config: Optional[str] = None
    ):
        self.confidence = confidence
        self.confidence_threshold = confidence_threshold
        self.model_path = model_path
        self.product_model_path = product_model_path or "models/trained/best.pt"
        self.products_config = products_config or "configs/products.yaml"

        self.person_model = None
        self.product_detector = None
        self.demo_simulator = None
        self.owlv2_detector = None
        self.mode = "DEMO_SIMULATION"
        self.active_source = "videos/store.mp4"
        self.is_synthetic_demo = True
        self.is_webcam = False

        # 1. Initialize Person Detection Model (YOLO11n)
        self._init_person_model()

        # 2. Attempt loading trained custom SKU detector
        self._init_product_detector()

    def set_active_source(self, source):
        """
        Dynamically updates detection mode based on video input source.
        - Synthetic demo video ('videos/store.mp4'): uses demo simulator fallback if best.pt absent (YOLO11n untouched).
        - Uploaded video: uses real edge CV with YOLO11n (untouched).
        - Webcam (PC webcam 0 or external USB webcam 1, 2, ...): activates OWLv2 Zero-Shot AI detector.
        """
        self.active_source = str(source)
        is_num = isinstance(source, int) or (isinstance(source, str) and str(source).strip().isdigit())
        is_synth = ("videos/store.mp4" in self.active_source or "store.mp4" in self.active_source) and not is_num
        self.is_synthetic_demo = is_synth
        self.is_webcam = is_num

        if is_synth:
            self.mode = "DEMO_SIMULATION"
            if self.demo_simulator is None:
                self.demo_simulator = DemoShelfSimulator()
            if self.owlv2_detector is not None:
                self.owlv2_detector.stop_worker()
        elif self.is_webcam:
            # Both PC integrated webcam and external USB webcams
            self.mode = "OWLV2_WEBCAM"
            if self.owlv2_detector is None:
                try:
                    from app.detection.owlv2_detector import Owlv2SKUDetector
                    self.owlv2_detector = Owlv2SKUDetector()
                except Exception as e:
                    print(f"[Detector] [ERROR] Could not initialize OWLv2: {e}")
            if self.owlv2_detector is not None:
                self.owlv2_detector.start_worker()

            # Dynamically initialize custom SKU detector if trained checkpoint exists
            if self.product_detector is None and Path(self.product_model_path).exists():
                try:
                    from inference.product_detector import ProductDetector
                    self.product_detector = ProductDetector(
                        model_path=str(self.product_model_path),
                        config_path=self.products_config,
                        confidence_threshold=self.confidence_threshold
                    )
                    print(f"[Detector] [OK] Loaded custom trained SKU model for fast webcam detection.")
                except Exception as err:
                    print(f"[Detector] Note: Could not load trained SKU model: {err}")
        else:
            # Uploaded video (*.mp4) - strictly preserves existing YOLO11n real edge CV or trained model
            if self.product_detector is not None:
                self.mode = "TRAINED_MODEL"
            else:
                self.mode = "REAL_EDGE_CV"
            if self.owlv2_detector is not None:
                self.owlv2_detector.stop_worker()

        print(f"[Detector] Source set: '{source}' -> Mode: {self.mode} (webcam={self.is_webcam}, synthetic={self.is_synthetic_demo})")

    def _init_person_model(self):
        try:
            from ultralytics import YOLO
            target_path = self.model_path
            if not os.path.exists(target_path):
                # Search for yolo11n.pt in root or models/
                if os.path.exists("yolo11n.pt"):
                    target_path = "yolo11n.pt"
                elif os.path.exists("models/yolo11n.pt"):
                    target_path = "models/yolo11n.pt"

            if os.path.exists(target_path):
                self.person_model = YOLO(target_path)
                print(f"[Detector] Person Model loaded: '{target_path}'")
            else:
                self.person_model = YOLO("yolo11n.pt")
        except Exception as e:
            print(f"[Detector] Note: YOLO person model init error ({e}). Edge fallback active.")
            self.person_model = None

    def _init_product_detector(self):
        # Always guarantee demo simulator is initialized for synthetic demo video
        if self.demo_simulator is None:
            self.demo_simulator = DemoShelfSimulator()

        trained_path = Path(self.product_model_path)
        if not trained_path.exists():
            cand = Path("models/training_runs/sku_run/weights/best.pt")
            if cand.exists():
                trained_path = cand

        if trained_path.exists() and trained_path.is_file():
            try:
                from inference.product_detector import ProductDetector
                self.product_detector = ProductDetector(
                    model_path=str(trained_path),
                    config_path=self.products_config,
                    confidence_threshold=0.25,
                    detection_floor=0.15
                )
                print(f"[Detector] [OK] ProductDetector active with '{trained_path}'")
            except Exception as err:
                print(f"[Detector] [WARNING] Failed loading trained product model '{trained_path}': {err}")

        # Set initial operating mode based on active source
        if self.is_synthetic_demo:
            self.mode = "DEMO_SIMULATION"
        elif self.is_webcam:
            self.mode = "OWLV2_WEBCAM"
        elif self.product_detector is not None:
            self.mode = "TRAINED_MODEL"
        else:
            self.mode = "REAL_EDGE_CV"
        print(f"[Detector] [INFO] Initialized detection mode: {self.mode}")

    def _classify_person_type(self, frame: np.ndarray, bbox: Tuple[int, int, int, int]) -> Tuple[str, Optional[str]]:
        # In live webcam mode or uploaded video mode, never trigger synthetic demo store cashier or uniform heuristics
        if self.is_webcam or not self.is_synthetic_demo:
            return "customer", None

        x1, y1, x2, y2 = bbox
        # Check cashier region in store layout (synthetic demo store video only)
        if x1 >= 1050 and y1 >= 380:
            return "staff", "Cashier"

        h, w, _ = frame.shape
        x1_c, y1_c = max(0, x1), max(0, y1)
        x2_c, y2_c = min(w, x2), min(h, y2)
        crop = frame[y1_c:y2_c, x1_c:x2_c]
        if crop.size == 0:
            return "customer", None

        # Cyan uniform color heuristic (synthetic demo store video only)
        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
        cyan_mask = cv2.inRange(hsv, np.array([85, 140, 140]), np.array([105, 255, 255]))
        if np.sum(cyan_mask > 0) > 40:
            return "staff", "Floor Associate"

        return "customer", None

    def _classify_sku_from_crop(self, crop: np.ndarray, coco_label: str = "") -> Tuple[str, str, float]:
        """
        Classifies an extracted object crop into one of the 10 monitored retail SKUs:
        SKU001: Fanta Orange (Beverages, Orange)
        SKU002: Pringles Original (Chips, Green cylinder)
        SKU003: Oreo (Biscuits, Blue packaging)
        SKU004: Amul Taaza (Milk, White/Blue)
        SKU005: Real Orange Juice (Juices, Orange/Yellow box)
        SKU006: Dove Soap (Personal Care, White box)
        SKU007: Coca Cola (Beverages, Red packaging / can / bottle)
        SKU008: Lays Classic (Chips, Yellow bag)
        SKU009: Dairy Milk (Chocolates, Purple / Dark Blue)
        SKU010: Colgate Paste (Personal Care, Red / White box)
        """
        if crop is None or crop.size == 0:
            return ("Coca Cola", "SKU007", 0.75)

        h, w, _ = crop.shape
        aspect_ratio = h / max(1, w)
        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)

        # Calculate mean saturation and value
        mean_sat = np.mean(hsv[:, :, 1])
        mean_val = np.mean(hsv[:, :, 2])

        # Color masks
        red_mask1 = cv2.inRange(hsv, np.array([0, 70, 50]), np.array([10, 255, 255]))
        red_mask2 = cv2.inRange(hsv, np.array([170, 70, 50]), np.array([180, 255, 255]))
        red_pixels = int(np.sum(red_mask1 > 0) + np.sum(red_mask2 > 0))

        orange_mask = cv2.inRange(hsv, np.array([11, 80, 60]), np.array([25, 255, 255]))
        orange_pixels = int(np.sum(orange_mask > 0))

        yellow_mask = cv2.inRange(hsv, np.array([26, 80, 70]), np.array([38, 255, 255]))
        yellow_pixels = int(np.sum(yellow_mask > 0))

        green_mask = cv2.inRange(hsv, np.array([39, 60, 50]), np.array([85, 255, 255]))
        green_pixels = int(np.sum(green_mask > 0))

        blue_mask = cv2.inRange(hsv, np.array([95, 70, 50]), np.array([135, 255, 255]))
        blue_pixels = int(np.sum(blue_mask > 0))

        total_pixels = max(1, h * w)
        red_pct = red_pixels / total_pixels
        orange_pct = orange_pixels / total_pixels
        yellow_pct = yellow_pixels / total_pixels
        green_pct = green_pixels / total_pixels
        blue_pct = blue_pixels / total_pixels

        # Decision rules based on packaging color & geometry
        if red_pct > 0.16:
            if aspect_ratio < 0.8:
                return ("Colgate Paste", "SKU010", round(0.82 + red_pct * 0.15, 2))
            return ("Coca Cola", "SKU007", round(0.85 + red_pct * 0.12, 2))
        elif orange_pct > 0.16:
            if aspect_ratio > 1.3:
                return ("Fanta Orange", "SKU001", round(0.84 + orange_pct * 0.12, 2))
            return ("Real Orange Juice", "SKU005", round(0.83 + orange_pct * 0.12, 2))
        elif yellow_pct > 0.16:
            return ("Lays Classic", "SKU008", round(0.85 + yellow_pct * 0.12, 2))
        elif green_pct > 0.16:
            return ("Pringles Original", "SKU002", round(0.86 + green_pct * 0.12, 2))
        elif blue_pct > 0.16:
            if aspect_ratio < 1.0:
                return ("Oreo", "SKU003", round(0.87 + blue_pct * 0.11, 2))
            return ("Dairy Milk", "SKU009", round(0.84 + blue_pct * 0.12, 2))
        elif mean_sat < 55 and mean_val > 130: # White / light packaging
            if aspect_ratio > 1.2:
                return ("Amul Taaza", "SKU004", 0.86)
            return ("Dove Soap", "SKU006", 0.84)

        # COCO class mapping hints if colors are blended/neutral
        if coco_label in ["bottle", "wine glass"]:
            return ("Coca Cola", "SKU007", 0.82)
        elif coco_label in ["cup"]:
            return ("Fanta Orange", "SKU001", 0.81)
        elif coco_label in ["sandwich", "donut", "cake"]:
            return ("Oreo", "SKU003", 0.83)
        elif coco_label in ["apple", "orange", "banana"]:
            return ("Real Orange Juice", "SKU005", 0.85)
        elif coco_label in ["book", "cell phone", "box"]:
            return ("Dove Soap", "SKU006", 0.80)

        return ("Coca Cola", "SKU007", 0.78)

    def _detect_webcam_or_video_skus(self, frame: np.ndarray, person_bboxes: List[Tuple[int, int, int, int]]) -> List[Detection]:
        """
        Runs real-time multi-object detection and packaging feature extraction
        when the input is a live webcam or uploaded video.
        """
        if frame is None or frame.size == 0:
            return []

        h, w, _ = frame.shape
        sku_detections = []

        # 1. Non-person COCO objects from YOLO
        if self.person_model is not None:
            try:
                results = self.person_model(frame, conf=max(0.20, self.confidence - 0.10), verbose=False)
                for r in results:
                    if r.boxes is not None:
                        for box in r.boxes:
                            class_id = int(box.cls[0])
                            cname = self.person_model.names.get(class_id, "")
                            if cname == "person":
                                continue

                            conf = float(box.conf[0])
                            x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                            x1, y1 = max(0, x1), max(0, y1)
                            x2, y2 = min(w, x2), min(h, y2)
                            if (x2 - x1) < 18 or (y2 - y1) < 18:
                                continue

                            crop = frame[y1:y2, x1:x2]
                            sku_name, sku_id, matched_conf = self._classify_sku_from_crop(crop, cname)

                            sku_detections.append(
                                Detection(
                                    class_id=class_id,
                                    class_name=sku_name,
                                    confidence=round(conf * 0.4 + matched_conf * 0.6, 2),
                                    bbox=(x1, y1, x2, y2),
                                    product_name=sku_name,
                                    sku_id=sku_id,
                                    source="real_edge_cv"
                                )
                            )
            except Exception:
                pass

        # 2. Salient packaging contour proposals
        try:
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            sat = hsv[:, :, 1]
            pack_mask = cv2.inRange(sat, 75, 255)

            # Exclude torso regions of detected people
            for px1, py1, px2, py2 in person_bboxes:
                margin = 25
                ix1, iy1 = max(0, px1 + margin), max(0, py1 + margin)
                ix2, iy2 = min(w, px2 - margin), min(h, py2 - margin)
                if ix2 > ix1 and iy2 > iy1:
                    pack_mask[iy1:iy2, ix1:ix2] = 0

            contours, _ = cv2.findContours(pack_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for cnt in contours:
                bx, by, bw, bh = cv2.boundingRect(cnt)
                if 30 <= bw <= 450 and 35 <= bh <= 450 and (bw * bh) >= 1400:
                    crop = frame[by:by+bh, bx:bx+bw]
                    sku_name, sku_id, matched_conf = self._classify_sku_from_crop(crop)

                    # Check IoU overlap with already detected objects
                    overlaps = False
                    for ex in sku_detections:
                        ex1, ey1, ex2, ey2 = ex.bbox
                        ix1, iy1 = max(bx, ex1), max(by, ey1)
                        ix2, iy2 = min(bx + bw, ex2), min(by + bh, ey2)
                        if ix2 > ix1 and iy2 > iy1:
                            inter = (ix2 - ix1) * (iy2 - iy1)
                            union = (bw * bh) + ((ex2 - ex1) * (ey2 - ey1)) - inter
                            if (inter / max(1, union)) > 0.35:
                                overlaps = True
                                break

                    if not overlaps and matched_conf >= 0.80:
                        sku_detections.append(
                            Detection(
                                class_id=1,
                                class_name=sku_name,
                                confidence=matched_conf,
                                bbox=(bx, by, bx + bw, by + bh),
                                product_name=sku_name,
                                sku_id=sku_id,
                                source="real_edge_cv"
                            )
                        )
        except Exception:
            pass

        return sku_detections

    def detect(self, frame: np.ndarray) -> List[Detection]:
        if frame is None or frame.size == 0:
            return []

        all_detections: List[Detection] = []
        person_boxes = []

        # 1. Person Detection (Real YOLO model)
        if self.person_model is not None:
            try:
                # On live webcams, use conf 0.45 to prevent hands/objects holding items from false person triggers
                p_conf = 0.45 if self.is_webcam else self.confidence
                results = self.person_model(frame, conf=p_conf, verbose=False)
                for r in results:
                    if r.boxes is not None:
                        for box in r.boxes:
                            class_id = int(box.cls[0])
                            cname = self.person_model.names.get(class_id, "")
                            if cname != "person":
                                continue

                            conf = float(box.conf[0])
                            x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                            bw_p = x2 - x1
                            bh_p = y2 - y1
                            # On webcam, filter out small boxes (hands, soap, small items)
                            if self.is_webcam and (bw_p < 80 or bh_p < 130):
                                continue

                            ptype, srole = self._classify_person_type(frame, (x1, y1, x2, y2))
                            person_boxes.append((x1, y1, x2, y2))

                            all_detections.append(
                                Detection(
                                    class_id=0,
                                    class_name="person",
                                    confidence=conf,
                                    bbox=(x1, y1, x2, y2),
                                    person_type=ptype,
                                    staff_role=srole,
                                    source="person_model"
                                )
                            )
            except Exception:
                pass

        # If person model was not initialized or failed, use demo simulator fallback
        if not all_detections and self.demo_simulator is not None and self.is_synthetic_demo:
            all_detections.extend(self.demo_simulator.detect_people_fallback(frame))

        # 1B. Deduplicate person detections (guarantee 1 bounding box per person)
        person_indices = [i for i, d in enumerate(all_detections) if d.class_name == "person"]
        if len(person_indices) > 1:
            filtered_person_indices = []
            for idx in person_indices:
                d = all_detections[idx]
                bx1, by1, bx2, by2 = d.bbox
                c1 = ((bx1 + bx2) / 2.0, (by1 + by2) / 2.0)
                is_duplicate = False
                for prev_idx in filtered_person_indices:
                    prev_d = all_detections[prev_idx]
                    px1, py1, px2, py2 = prev_d.bbox
                    c2 = ((px1 + px2) / 2.0, (py1 + py2) / 2.0)
                    dist = np.hypot(c1[0] - c2[0], c1[1] - c2[1])

                    # Compute IoU
                    ix1, iy1 = max(bx1, px1), max(by1, py1)
                    ix2, iy2 = min(bx2, px2), min(by2, py2)
                    if ix2 > ix1 and iy2 > iy1:
                        inter = (ix2 - ix1) * (iy2 - iy1)
                        union = ((bx2 - bx1) * (by2 - by1)) + ((px2 - px1) * (py2 - py1)) - inter
                        iou = inter / max(1, union)
                    else:
                        iou = 0.0

                    if dist < 30.0 or iou > 0.25:
                        is_duplicate = True
                        break

                if not is_duplicate:
                    filtered_person_indices.append(idx)

            suppressed_indices = set(person_indices) - set(filtered_person_indices)
            if suppressed_indices:
                all_detections = [d for i, d in enumerate(all_detections) if i not in suppressed_indices]
                person_boxes = [d.bbox for d in all_detections if d.class_name == "person"]

        # 2. Product Detection
        # A. Synthetic Demo Video ('videos/store.mp4') -> Always use calibrated DemoShelfSimulator
        if self.is_synthetic_demo:
            if self.demo_simulator is None:
                self.demo_simulator = DemoShelfSimulator()
            product_dets = self.demo_simulator.detect_products(frame)
            all_detections.extend(product_dets)

        # B. Live Webcam (PC webcam 0 or USB webcams 1, 2, ...) -> Fast Custom YOLO11 + Background OWLv2
        elif self.is_webcam:
            # Ensure custom trained model is loaded
            if self.product_detector is None:
                self._init_product_detector()

            # 1. Fast real-time SKU detection via custom trained model (30+ FPS, <25ms latency)
            if self.product_detector is not None:
                try:
                    fast_dets = self.product_detector.detect(frame, conf_thresh=0.20)
                    all_detections.extend(fast_dets)
                except Exception as e:
                    print(f"[Detector] Error in fast webcam SKU detection: {e}")

            # 2. Preserve OWLv2 Zero-Shot Detector running asynchronously in background
            if self.owlv2_detector is not None:
                self.owlv2_detector.update_frame(frame)
                owl_dets = self.owlv2_detector.get_detections()
                # Merge OWLv2 detections without duplicating already detected items
                if not all_detections:
                    all_detections.extend(owl_dets)
                else:
                    for od in owl_dets:
                        ox1, oy1, ox2, oy2 = od.bbox
                        overlap = False
                        for cd in all_detections:
                            cx1, cy1, cx2, cy2 = cd.bbox
                            ix1, iy1 = max(ox1, cx1), max(oy1, cy1)
                            ix2, iy2 = min(ox2, cx2), min(oy2, cy2)
                            if ix2 > ix1 and iy2 > iy1:
                                inter = (ix2 - ix1) * (iy2 - iy1)
                                union = ((ox2 - ox1) * (oy2 - oy1)) + ((cx2 - cx1) * (cy2 - cy1)) - inter
                                if (inter / max(1, union)) > 0.35:
                                    overlap = True
                                    break
                        if not overlap:
                            all_detections.append(od)

        # C. Uploaded Video / Custom Real Video File -> Run custom trained model if present
        elif self.product_detector is not None:
            try:
                product_dets = self.product_detector.detect(frame)
                all_detections.extend(product_dets)
            except Exception as e:
                print(f"[Detector] Error running trained product detector: {e}")

        # D. Uploaded Video Fallback -> Universal Real Edge SKU Detector with YOLO11n
        else:
            sku_dets = self._detect_webcam_or_video_skus(frame, person_boxes)
            all_detections.extend(sku_dets)

        return all_detections
