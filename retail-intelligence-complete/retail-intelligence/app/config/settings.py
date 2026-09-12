from pathlib import Path
import os

ROOT_DIR = Path(__file__).resolve().parents[2]

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT_DIR / ".env")
except ImportError:
    pass

MODELS_DIR = ROOT_DIR / "models"
DATA_DIR = ROOT_DIR / "data"
VIDEO_DIR = ROOT_DIR / "videos"
OUTPUT_DIR = ROOT_DIR / "output"
DASHBOARD_DIR = ROOT_DIR / "dashboard"

YOLO_MODEL = os.getenv("YOLO_MODEL", str(MODELS_DIR / "yolo11n.pt"))
PRODUCT_MODEL = os.getenv("PRODUCT_MODEL", str(MODELS_DIR / "trained" / "best.pt"))
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.75"))
PRODUCTS_CONFIG = os.getenv("PRODUCTS_CONFIG", str(ROOT_DIR / "configs" / "products.yaml"))

CONFIDENCE = float(os.getenv("CONFIDENCE", "0.35"))

def _get_default_camera_source():
    env_source = os.getenv("CAMERA_SOURCE")
    if env_source is not None and env_source != "":
        if str(env_source).isdigit():
            return int(env_source)
        return env_source
    
    # Auto-detect if physical webcam device 0 is connected and operational
    try:
        import cv2
        cap = cv2.VideoCapture(0)
        if cap.isOpened():
            ret, _ = cap.read()
            cap.release()
            if ret:
                return 0
    except Exception:
        pass
        
    return str(VIDEO_DIR / "store.mp4")

CAMERA_SOURCE = _get_default_camera_source()

DB_PATH = os.getenv("DB_PATH", str(DATA_DIR / "retail.db"))

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

LOW_STOCK_DEFAULT = int(os.getenv("LOW_STOCK_DEFAULT", "2"))
QUEUE_ALERT_THRESHOLD = int(os.getenv("QUEUE_ALERT_THRESHOLD", "4"))

STORE_CITY = os.getenv("STORE_CITY", "Morbi")
STORE_REGION = os.getenv("STORE_REGION", "Gujarat")
STORE_COUNTRY = os.getenv("STORE_COUNTRY", "India")
STORE_LAT = float(os.getenv("STORE_LAT", "22.8173"))
STORE_LON = float(os.getenv("STORE_LON", "70.8377"))
