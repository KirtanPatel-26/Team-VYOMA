"""
SmartRetail AI - Theft & Suspicious Activity Detection Package
==============================================================
Production-ready loss prevention and suspicious product-removal intelligence engine.
"""

from app.theft.config import TheftConfig, get_theft_config, update_theft_config
from app.theft.zones import StoreZoneManager
from app.theft.risk_engine import RiskScoringEngine, RiskLevel
from app.theft.engine import TheftDetectionEngine

__all__ = [
    "TheftConfig",
    "get_theft_config",
    "update_theft_config",
    "StoreZoneManager",
    "RiskScoringEngine",
    "RiskLevel",
    "TheftDetectionEngine"
]
