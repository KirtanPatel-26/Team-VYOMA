import os
import json
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional

from app.config.settings import DATA_DIR

CONFIG_FILE = DATA_DIR / "theft_config.json"

@dataclass
class TheftConfig:
    enabled: bool = True
    theft_risk_threshold: int = 60
    high_risk_threshold: int = 80
    product_missing_seconds: float = 2.0
    min_shelf_interaction_seconds: float = 1.5
    
    # Risk score adjustments
    score_pickup: int = 20
    score_disappeared: int = 25
    score_leave_shelf: int = 15
    score_move_to_exit: int = 20
    score_enter_exit: int = 30
    score_no_checkout: int = 30
    score_return_product: int = -40
    score_reappear: int = -30
    score_checkout: int = -50
    
    # Classification thresholds
    normal_max: int = 29
    low_risk_max: int = 59
    suspicious_max: int = 79
    high_risk_min: int = 80

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TheftConfig":
        valid_keys = cls.__dataclass_fields__.keys()
        filtered = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered)

_current_config: Optional[TheftConfig] = None

def load_theft_config() -> TheftConfig:
    global _current_config
    config = TheftConfig()

    # Environment variables take precedence if present
    env_enabled = os.getenv("THEFT_ENABLED")
    if env_enabled is not None:
        config.enabled = env_enabled.lower() in ("true", "1", "yes")

    env_risk_thresh = os.getenv("THEFT_RISK_THRESHOLD")
    if env_risk_thresh is not None and env_risk_thresh.isdigit():
        config.theft_risk_threshold = int(env_risk_thresh)

    env_high_thresh = os.getenv("HIGH_RISK_THRESHOLD")
    if env_high_thresh is not None and env_high_thresh.isdigit():
        config.high_risk_threshold = int(env_high_thresh)

    env_missing_sec = os.getenv("PRODUCT_MISSING_SECONDS")
    if env_missing_sec is not None:
        try:
            config.product_missing_seconds = float(env_missing_sec)
        except ValueError:
            pass

    # Load from persistent JSON file if available
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved_data = json.load(f)
                config = TheftConfig.from_dict(saved_data)
        except Exception as e:
            print(f"[TheftConfig] Warning reading config file: {e}")

    _current_config = config
    return config

def save_theft_config(config: TheftConfig) -> bool:
    global _current_config
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config.to_dict(), f, indent=2)
        _current_config = config
        return True
    except Exception as e:
        print(f"[TheftConfig] Error saving config file: {e}")
        return False

def get_theft_config() -> TheftConfig:
    global _current_config
    if _current_config is None:
        return load_theft_config()
    return _current_config

def update_theft_config(new_params: Dict[str, Any]) -> TheftConfig:
    cfg = get_theft_config()
    curr_dict = cfg.to_dict()
    for k, v in new_params.items():
        if k in curr_dict:
            curr_dict[k] = v
    updated = TheftConfig.from_dict(curr_dict)
    save_theft_config(updated)
    return updated
