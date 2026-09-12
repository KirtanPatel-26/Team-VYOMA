# SmartRetail AI — Edge-AI SKU Model Training & Deployment Guide

> **SIH Problem Statement**: Edge-AI Retail Analytics (Shopper Analytics + Inventory + Queue Intelligence)  
> **Platform Version**: 2.0.0 Architecture  
> **Operating Modes**: `TRAINED_MODEL` (Custom 10-SKU Neural Network) & `DEMO_SIMULATION` (Transparent Fallback)

---

## 1. Executive Architecture Overview

In version 1.0 of the retail intelligence platform, object detection relied on reverse-engineered OpenCV HSV color masks mapped at hard-coded screen coordinates. While functional for demonstrating visual dashboard widgets on a synthetic OpenCV video, such color-hacks fail completely in real camera deployments under variable store lighting, camera angles, and genuine packaging.

Version 2.0 introduces a **genuine, end-to-end trainable computer vision pipeline**:

```
CCTV / RTSP / Webcam / Mobile Video
                 │
                 ▼
 ┌──────────────────────────────────────┐
 │      ObjectDetector Orchestrator     │  (app/detection/detector.py)
 │  ├─ Person Model  → YOLO11n (Real)   │  (Customer & Staff detection, always active)
 │  └─ Product Model → One of:          │
 │       ✅ ProductDetector (Trained)   │  (Active if models/trained/best.pt exists)
 │       ⚠️ DemoShelfSimulator (Fallback)│ (Active if weights absent, explicitly labeled)
 └──────────────────────────────────────┘
                 │
                 ▼  Detection(..., source="trained_sku_model" | "demo_simulation")
     Centroid Tracker + Spatial Shelf Filter
                 │
                 ▼
        Temporal Smoother                (app/inventory/smoothing.py — median filtering)
                 │
                 ▼
 Stock Analyzer · Planogram Compliance · Queue & Traffic Analytics
                 │
                 ├─────────────────────────┬─────────────────────────┐
                 ▼                         ▼                         ▼
         FastAPI Endpoints          2D Operations Hub        3D Digital Twin
            (/api/...)             (/dashboard/index.html)   (/dashboard/3d/index.html)
```

### The Honest System Guarantee
1. **Zero Fake Brand Mapping**: The system strictly forbids arbitrary mapping of generic COCO labels to brand names (e.g. COCO class `bottle` cannot be mapped to `Fanta Orange`).
2. **Explicit Attribution**: Every detection carries a `source` tag (`trained_sku_model`, `person_model`, or `demo_simulation`).
3. **Telemetry Transparency**: The system state reports `detection_mode: "TRAINED_MODEL"` when custom weights are loaded, or `detection_mode: "DEMO_SIMULATION"` when running fallback heuristics on the synthetic demo video.

---

## 2. Monitored 10-SKU Retail Catalog

All product metadata is synchronized between [`configs/products.yaml`](file:///configs/products.yaml) and [`data/products.json`](file:///data/products.json):

| Class ID | SKU Code | Product Name | Category | Shelf Zone | Min Stock | Price |
|---|---|---|---|---|---|---|
| **0** | `SKU001` | **Fanta Orange** | Beverages | Beverages & Juices | 2 | ₹35 |
| **1** | `SKU002` | **Pringles Original** | Chips | Snacks & Biscuits | 2 | ₹110 |
| **2** | `SKU003` | **Oreo** | Biscuits | Snacks & Biscuits | 2 | ₹30 |
| **3** | `SKU004` | **Amul Taaza** | Milk | Dairy & Essentials | 3 | ₹30 |
| **4** | `SKU005` | **Real Orange Juice** | Juices | Beverages & Juices | 2 | ₹40 |
| **5** | `SKU006` | **Dove Soap** | Soap | Dairy & Essentials | 2 | ₹40 |
| **6** | `SKU007` | **Coca Cola** | Beverages | Beverages & Juices | 2 | ₹40 |
| **7** | `SKU008` | **Lays Classic** | Chips | Snacks & Biscuits | 3 | ₹20 |
| **8** | `SKU009` | **Dairy Milk** | Chocolates | Snacks & Biscuits | 2 | ₹50 |
| **9** | `SKU010` | **Colgate Paste** | Personal Care | Dairy & Essentials | 2 | ₹55 |

---

## 3. Dataset Collection Guidelines

To train a robust SKU model capable of deploying in real store aisles, collect **150–250 images per SKU** using the following protocol:

### Diversity Checklist
- **Rotation & Angle**: Photograph products from front, 45-degree angle, side, and high-angle (simulating ceiling-mounted CCTV cameras at 2.5m–3.5m height).
- **Lighting Variation**: Capture under bright ceiling fluorescent lighting, warm spotlights, and low-light / night conditions.
- **Packaging Reflection**: For glossy packaging (Amul milk pouches, Lays metallic foil bags), capture frames with glare and specular highlights.
- **Occlusions**: Include frames where products are partially blocked by shelf edges, price tags, or shoppers' hands (10% to 50% occlusion).
- **Context**: 
  - 40% Isolated photos (single item on counter or turn-table)
  - 60% In-situ shelf photos (multiple adjacent products on physical retail shelving)

### Recording Session Prefixing
Always record walkthrough videos in separate sessions. When running the frame extractor, designate a distinct session prefix per recording:

```bash
# Morning shelf walkthrough with Phone 1
python scripts/extract_frames.py --input raw_videos/morning_cam1.mp4 --output datasets/products/raw/images --interval 10 --prefix sessionA_cam1

# Afternoon shelf walkthrough with Phone 2
python scripts/extract_frames.py --input raw_videos/afternoon_cam2.mp4 --output datasets/products/raw/images --interval 8 --prefix sessionB_cam2
```

The session prefix is critical: it enables `prepare_dataset.py` to **group frames by session**, ensuring that near-duplicate frames from the same video clip do not leak across the train and test splits.

---

## 4. Annotation Workflow (CVAT & Roboflow)

Annotations must adhere to standard YOLO bounding box format (`class_id x_center y_center width height` normalized between 0.0 and 1.0).

### Recommended Tool: Roboflow (Fastest) or CVAT (Self-Hosted)
1. Create a project named `smartretail-10sku`.
2. Add the 10 classes in the exact order specified in `configs/products.yaml` (0: Fanta Orange, 1: Pringles Original, ..., 9: Colgate Paste).
3. Draw tight bounding boxes around each visible product instance.
4. Export annotations in **YOLOv8 / YOLO11 PyTorch TXT** format.
5. Place the resulting files into:
   - Images: `datasets/products/raw/images/`
   - Labels: `datasets/products/raw/labels/`

Example label line in `datasets/products/raw/labels/sessionA_cam1_00012.txt`:
```
0 0.4523 0.6120 0.0841 0.1942
```
*(Meaning: Class 0 = Fanta Orange, centered at (45.2%, 61.2%) with width 8.4% and height 19.4% of image dimensions).*

---

## 5. End-to-End Command Execution Pipeline

### Step 1: Split Dataset (Leakage-Safe Partitioning)
Partitions the dataset into 70% Train, 20% Validation, and 10% Independent Test splits:
```bash
python scripts/prepare_dataset.py
```

### Step 2: Validate Dataset Quality
Scans all images and labels for corrupted files, invalid coordinates, class ID mismatches, and reports per-class balance:
```bash
python scripts/validate_dataset.py
```
*(Exit code 0 confirms all annotations and files are 100% valid).*

### Step 3: Train the Custom 10-SKU Model
Executes transfer learning from YOLO11n using retail-specific augmentations configured in `configs/training.yaml`:
```bash
python scripts/train.py --model yolo11n.pt --epochs 100 --batch 16 --imgsz 640
```
- Automatically saves `models/trained/best.pt`, `models/trained/last.pt`, and `models/trained/metadata.json`.
- The live FastAPI application immediately detects and boots with `best.pt` on subsequent startups.

### Step 4: Independent Test Evaluation
Computes precision, recall, mAP@0.50, and mAP@0.50:0.95 strictly on the **unseen test split**:
```bash
python scripts/evaluate.py --model models/trained/best.pt --split test
```
- Outputs metrics to console table.
- Generates machine-readable `reports/metrics.json`.
- Copies confusion matrix to `reports/confusion_matrix.png`.
- Builds standalone executive visual report at `reports/evaluation_report.html`.

### Step 5: Test Inference on Real Photos
Test the model on an arbitrary image, video, or webcam:
```bash
# Single image
python scripts/predict.py --model models/trained/best.pt --source test_shelf.jpg

# Live webcam preview
python scripts/predict.py --model models/trained/best.pt --source 0 --show

# RTSP IP Camera stream
python scripts/predict.py --model models/trained/best.pt --source rtsp://admin:pass@192.168.1.100:554/stream1
```

### Step 6: Edge Hardware Performance Benchmark
Measures actual FPS, latency distribution (mean, median, p95), CPU%, and RAM usage on your deployment machine:
```bash
python scripts/benchmark.py --model models/trained/best.pt --rounds 100
```

### Step 7: Export to ONNX / TensorRT for Edge Deployment
Export weights for execution on low-power edge accelerators (Nvidia Jetson Orin/Nano, Intel NUC):
```bash
python scripts/export.py --model models/trained/best.pt --format onnx --dynamic
```

---

## 6. How to Add an 11th SKU (Step-by-Step)

To expand the monitored catalog to an 11th product (e.g., `SKU011: Nescafe Classic`):

1. **Update `configs/products.yaml`**:
   - Change `nc: 11`
   - Add `10: "Nescafe Classic"` under `names`
   - Add `10: "SKU011"` under `sku_ids`
   - Add category and default shelf under `metadata`
2. **Update `data/products.json`**:
   - Add the JSON object for `SKU011` with `id`, `name`, `category`, `price`, `minimum_stock`, and `target_shelf_zone`.
3. **Collect and Annotate**:
   - Collect 150+ photos of the new product, annotate with class ID `10`.
   - Run `python scripts/prepare_dataset.py` and `python scripts/validate_dataset.py`.
4. **Retrain Model**:
   - Run `python scripts/train.py --epochs 100`.
   - The new checkpoint in `models/trained/best.pt` will now detect all 11 SKUs.

---

## 7. Operational Modes in the Web Dashboard

| Mode | Trigger | Display Indicator | Description |
|---|---|---|---|
| **`TRAINED_MODEL`** | `models/trained/best.pt` exists and validates with 10 SKU classes | Glowing Green: `● TRAINED MODEL` | Real YOLO SKU inference running on live camera frames. |
| **`DEMO_SIMULATION`** | `models/trained/best.pt` missing or incompatible class count | Amber Warning: `▲ DEMO SIMULATION` | Relocated fallback color-heuristics operating on synthetic video. Explicitly labeled to preserve architectural honesty. |

Both the 2D Dashboard (`/dashboard/index.html`) and the 3D Digital Twin (`/dashboard/3d/index.html`) dynamically reflect this status via the `GET /api/status` endpoint.

---

## 8. Transparent Edge-AI Limitations

When presenting or deploying this system, acknowledge the following transparent edge constraints:
1. **Packaging Redesigns**: Neural object detectors learn visual packaging features. If a manufacturer alters packaging art (e.g. holiday special editions), new training samples must be added to maintain detection confidence.
2. **Extreme Occlusion**: Products occluded by more than 75% behind pillars or hands will drop below the 0.75 confidence threshold and be classified as `Unknown / Low Confidence`.
3. **Synthetic Video Scope**: The bundled video (`videos/store.mp4`) is a synthetic 2D geometric visualization. A model trained on real photos should be evaluated using real footage, webcams, or via the `POST /api/ai/detect` endpoint.
4. **Lighting Shadows**: Severe store power outages or deep shadows under low shelves may require supplementary infrared or LED shelf strip lighting for optimal edge CV accuracy.
