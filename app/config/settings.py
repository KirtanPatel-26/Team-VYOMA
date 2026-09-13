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

# Deployment Mode (Edge AI vs. Headless Cloud Hub)
# In cloud mode (RUN_EDGE_AI=false), OpenCV and PyTorch are skipped (<80MB RAM).
RUN_EDGE_AI = os.getenv("RUN_EDGE_AI", "true").lower() in ("true", "1", "yes")
ENVIRONMENT = os.getenv("ENVIRONMENT", "edge" if RUN_EDGE_AI else "cloud")

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

# AI Copilot, RAG & Gemini LLM Settings
KNOWLEDGE_DIR = DATA_DIR / "knowledge"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
COPILOT_DEFAULT_MODE = os.getenv("COPILOT_DEFAULT_MODE", "offline")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")

# Central Encryption Layer & Security Configuration
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", "")
ENCRYPTION_KEY_OLD = os.getenv("ENCRYPTION_KEY_OLD", "")
JWT_SECRET = os.getenv("JWT_SECRET", "")



