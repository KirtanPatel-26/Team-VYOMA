import os
import sys
from pathlib import Path
import yaml
import torch

ROOT_DIR = Path(__file__).resolve().parents[1]
CONFIGS_DIR = ROOT_DIR / "configs"
DATASETS_DIR = ROOT_DIR / "datasets"
MODELS_DIR = ROOT_DIR / "models"
REPORTS_DIR = ROOT_DIR / "reports"

# Ensure common directories exist
for p in [CONFIGS_DIR, DATASETS_DIR, MODELS_DIR / "trained", MODELS_DIR / "pretrained", REPORTS_DIR]:
    p.mkdir(parents=True, exist_ok=True)

def get_device() -> str:
    """Auto-detect optimal compute device (CUDA, MPS, or CPU)."""
    if torch.cuda.is_available():
        return "cuda"
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return "mps"
    return "cpu"

def load_products_config(path: str = None) -> dict:
    """Load products.yaml single source of truth."""
    config_file = Path(path) if path else CONFIGS_DIR / "products.yaml"
    if not config_file.exists():
        raise FileNotFoundError(f"Products configuration not found: {config_file}")
    with open(config_file, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def load_training_config(path: str = None) -> dict:
    """Load training.yaml configuration."""
    config_file = Path(path) if path else CONFIGS_DIR / "training.yaml"
    if not config_file.exists():
        raise FileNotFoundError(f"Training configuration not found: {config_file}")
    with open(config_file, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def get_sku_id_for_class_name(name: str, products_cfg: dict = None) -> str:
    """Look up SKU code (e.g. SKU001) for a given class name."""
    if products_cfg is None:
        products_cfg = load_products_config()
    names = products_cfg.get("names", {})
    sku_ids = products_cfg.get("sku_ids", {})
    
    # Try finding by name matching
    for idx, cname in names.items():
        if cname.lower() == name.lower():
            return sku_ids.get(idx, f"SKU{int(idx)+1:03d}")
    return None
