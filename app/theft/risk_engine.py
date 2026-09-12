import time
from enum import Enum
from typing import Dict, List, Tuple, Optional, Any
from app.theft.config import TheftConfig, get_theft_config
from app.theft.interaction import PersonState

class RiskLevel(str, Enum):
    NORMAL = "NORMAL"
    LOW = "LOW"
    SUSPICIOUS = "SUSPICIOUS"
    HIGH = "HIGH"

class TimelineEvent:
    def __init__(self, description: str, score_delta: int, current_score: int, timestamp: Optional[float] = None):
        self.timestamp = timestamp or time.time()
        self.time_str = time.strftime("%H:%M:%S", time.localtime(self.timestamp))
        self.description = description
        self.score_delta = score_delta
        self.current_score = current_score

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.time_str,
            "raw_time": round(self.timestamp, 2),
            "description": self.description,
            "score_delta": f"{'+' if self.score_delta > 0 else ''}{self.score_delta}" if self.score_delta != 0 else "0",
            "current_score": self.current_score
        }

class PersonRiskProfile:
    """Maintains behavioral risk indicators, trajectory progression, and timeline for a tracked individual."""
    def __init__(self, person_id: int, config: TheftConfig):
        self.person_id = person_id
        self.config = config
        self.risk_score: int = 0
        self.risk_level: RiskLevel = RiskLevel.NORMAL
        self.timeline: List[TimelineEvent] = []
        
        # Behavioral milestone flags to prevent duplicate score applications
        self.flag_shelf_pickup: bool = False
        self.flag_product_disappeared: bool = False
        self.flag_left_shelf: bool = False
        self.flag_moved_to_exit: bool = False
        self.flag_entered_exit: bool = False
        self.flag_no_checkout_penalty: bool = False
        self.flag_checkout_applied: bool = False

        # Products associated with this risk profile
        self.primary_product_name: Optional[str] = None
        self.primary_sku_id: Optional[str] = None
        self.primary_shelf_id: Optional[str] = None

    def add_timeline_event(self, description: str, score_delta: int):
        prev_score = self.risk_score
        self.risk_score = max(0, min(100, self.risk_score + score_delta))
        self._update_risk_level()
        self.timeline.append(TimelineEvent(description, score_delta, self.risk_score))

    def _update_risk_level(self):
        if self.risk_score >= self.config.high_risk_min:
            self.risk_level = RiskLevel.HIGH
        elif self.risk_score >= self.config.theft_risk_threshold:
            self.risk_level = RiskLevel.SUSPICIOUS
        elif self.risk_score > self.config.normal_max:
            self.risk_level = RiskLevel.LOW
        else:
            self.risk_level = RiskLevel.NORMAL

    def to_dict(self) -> Dict[str, Any]:
        return {
            "person_id": self.person_id,
            "risk_score": self.risk_score,
            "risk_level": self.risk_level.value,
            "product_name": self.primary_product_name or "Unknown Item",
            "sku_id": self.primary_sku_id or "SKU",
            "shelf_id": self.primary_shelf_id or "SHELF",
            "timeline": [e.to_dict() for e in self.timeline]
        }


class RiskScoringEngine:
    """
    Evaluates multi-factor spatial-temporal risk of product removal without checkout.
    Implements mitigations for false positives when products are returned or checkout occurs.
    """
    def __init__(self, config: Optional[TheftConfig] = None):
        self.config = config or get_theft_config()
        self.profiles: Dict[int, PersonRiskProfile] = {}

    def get_or_create_profile(self, person_id: int) -> PersonRiskProfile:
        if person_id not in self.profiles:
            self.profiles[person_id] = PersonRiskProfile(person_id, self.config)
        return self.profiles[person_id]

    def process_person_movement(self, person_state: PersonState, timestamp: float):
        profile = self.get_or_create_profile(person_state.person_id)

        # 1. Milestone: Person enters shelf zone & interacts
        if person_state.active_shelf_id and person_state.shelf_dwell_time >= self.config.min_shelf_interaction_seconds:
            if not profile.flag_shelf_pickup:
                profile.flag_shelf_pickup = True
                profile.primary_shelf_id = person_state.active_shelf_id
                profile.add_timeline_event(
                    f"Shopper entered and interacted with shelf {person_state.active_shelf_id}",
                    self.config.score_pickup
                )

        # 2. Milestone: Person leaves shelf area after taking product
        if profile.flag_product_disappeared and not person_state.active_shelf_id and not profile.flag_left_shelf:
            profile.flag_left_shelf = True
            profile.add_timeline_event(
                f"Shopper walked away from shelf area carrying potential item",
                self.config.score_leave_shelf
            )

        # 3. Milestone: Person enters Checkout Zone (Mitigation)
        if person_state.checkout_detected and not profile.flag_checkout_applied:
            profile.flag_checkout_applied = True
            profile.add_timeline_event(
                f"Shopper entered checkout queue/counter (Risk mitigated)",
                self.config.score_checkout
            )

        # 4. Milestone: Person approaches Exit Zone (Corridor between Shelf C & Billing Counter)
        if person_state.current_zone_type == "EXIT_ZONE" or person_state.exit_detected:
            if not profile.flag_entered_exit:
                profile.flag_entered_exit = True
                profile.add_timeline_event(
                    f"Shopper reached store exit corridor between Shelf C & Billing Counter",
                    self.config.score_enter_exit
                )

            # Critical Theft Escalation if no checkout / billing detected
            if not person_state.checkout_detected and not profile.flag_no_checkout_penalty:
                profile.flag_no_checkout_penalty = True
                # Escalate directly to HIGH RISK (at least 85)
                theft_penalty = max(self.config.score_no_checkout, self.config.high_risk_min - profile.risk_score + 5)
                profile.add_timeline_event(
                    "CRITICAL: Exited through corridor between Shelf C and Billing Counter without POS billing",
                    theft_penalty
                )
                if not profile.primary_shelf_id and person_state.interacted_shelves:
                    profile.primary_shelf_id = person_state.interacted_shelves[-1]
                if not profile.primary_product_name:
                    profile.primary_product_name = "Unpaid Store Merchandise"

    def process_product_removal_event(self, removal_event: Dict[str, Any]):
        person_id = removal_event.get("person_id")
        if person_id is None:
            return

        profile = self.get_or_create_profile(person_id)
        if not profile.flag_product_disappeared:
            profile.flag_product_disappeared = True
            profile.primary_product_name = removal_event.get("product_name", "Product")
            profile.primary_sku_id = removal_event.get("sku_id", "SKU")
            profile.primary_shelf_id = removal_event.get("shelf_id", "SHELF")

            profile.add_timeline_event(
                f"Item '{profile.primary_product_name}' disappeared from shelf after interaction",
                self.config.score_disappeared
            )

    def process_product_returned_event(self, return_event: Dict[str, Any]):
        person_id = return_event.get("person_id")
        if person_id is not None and person_id in self.profiles:
            profile = self.profiles[person_id]
            profile.flag_product_disappeared = False
            profile.add_timeline_event(
                f"Item '{return_event.get('product_name')}' placed back on shelf (False positive mitigated)",
                self.config.score_return_product + self.config.score_reappear
            )

    def get_active_risks(self) -> List[Dict[str, Any]]:
        return [
            p.to_dict() for p in self.profiles.values()
            if p.risk_score >= self.config.theft_risk_threshold
        ]
