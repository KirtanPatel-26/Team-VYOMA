# Retail Intelligence Platform

AI-powered retail analytics using edge-first computer vision.

## Features

- YOLO object detection
- Local video/webcam/CCTV input
- Lightweight object tracking
- Product/SKU recognition layer
- Inventory counting
- Low-stock and out-of-stock alerts
- Shopper/traffic analytics
- Queue congestion analytics
- Local SQLite event storage
- Optional Supabase cloud sync
- Browser dashboard

## Architecture

Camera -> YOLO -> Tracker -> Product Recognition
       -> Inventory -> Alerts -> Local Dashboard
                              -> Optional Supabase/HQ

## Setup

### 1. Create environment

Windows:

```bash
python -m venv venv
venv\Scripts\activate
```

Linux/macOS:

```bash
python -m venv venv
source venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Put the model here

```text
models/yolo11n.pt
```

Your existing model can be copied into that location.

### 4. Put the test video here

```text
videos/store.mp4
```

### 5. Run edge detection

```bash
python run.py
```

Press `q` to stop.

### 6. Run dashboard

```bash
uvicorn app.main:app --reload
```

Open:

```text
http://127.0.0.1:8000/
```

## Important

`yolo11n.pt` is normally a generic object-detection model. It can detect classes such as `person` and `bottle`, but it does NOT automatically know that a bottle is Fanta.

For true SKU recognition, train a custom YOLO model using your labelled retail product dataset and place the resulting model at:

```text
models/product_model.pt
```

Then update the detector configuration to use that model.

## Demo strategy

For the SIH prototype:

1. Run all inference locally.
2. Use `store.mp4` for a controlled demo.
3. Switch `CAMERA_SOURCE=0` for a webcam.
4. Keep SQLite/local analytics working without internet.
5. Sync selected aggregated events to Supabase when internet is available.
