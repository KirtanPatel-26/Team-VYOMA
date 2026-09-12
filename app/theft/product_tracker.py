import time
import math
from typing import Dict, List, Tuple, Optional, Any
from app.theft.zones import StoreZoneManager
from app.theft.interaction import InteractionTracker, PersonState

class TrackedProduct:
    """State of an individual product detected on or near a shelf."""
    def __init__(
        self,
        product_id: str,
        sku_id: str,
        product_name: str,
        shelf_id: str,
        bbox: Tuple[int, int, int, int],
        confidence: float,
        timestamp: float
    ):
        self.product_id = product_id
        self.sku_id = sku_id
        self.product_name = product_name
        self.shelf_id = shelf_id
        self.bbox = bbox
        self.confidence = confidence
        self.first_seen_time = timestamp
        self.last_seen_time = timestamp
        self.disappeared_time: Optional[float] = None
        self.current_status = "PRESENT" # "PRESENT", "POTENTIAL_REMOVAL", "REMOVED"
        self.associated_person_id: Optional[int] = None
        self.interaction_verified: bool = False

    @property
    def center(self) -> Tuple[float, float]:
        x1, y1, x2, y2 = self.bbox
        return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "product_id": self.product_id,
            "sku_id": self.sku_id,
            "product_name": self.product_name,
            "shelf_id": self.shelf_id,
            "confidence": round(self.confidence, 3),
            "bbox": list(self.bbox),
            "last_seen_time": round(self.last_seen_time, 2),
            "current_status": self.current_status,
            "associated_person_id": self.associated_person_id
        }

class ProductRemovalTracker:
    """
    Tracks inventory presence on shelves over time.
    Uses temporal logic to differentiate normal YOLO detection flickers
    from authentic human-mediated product pickups.
    """
    def __init__(
        self,
        zone_manager: StoreZoneManager,
        interaction_tracker: InteractionTracker,
        missing_seconds_threshold: float = 2.0,
        min_shelf_interaction_sec: float = 1.2
    ):
        self.zone_mgr = zone_manager
        self.interaction_tracker = interaction_tracker
        self.missing_seconds_threshold = missing_seconds_threshold
        self.min_shelf_interaction_sec = min_shelf_interaction_sec
        self.tracked_products: Dict[str, TrackedProduct] = {} # product_id -> TrackedProduct
        self.next_item_counter = 1

    def _match_or_create_product_id(
        self,
        sku_id: str,
        shelf_id: str,
        center: Tuple[float, float],
        max_dist: float = 60.0
    ) -> Optional[str]:
        best_id = None
        best_dist = max_dist

        for pid, tp in self.tracked_products.items():
            if tp.sku_id == sku_id and tp.shelf_id == shelf_id:
                d = math.dist(center, tp.center)
                if d < best_dist:
                    best_dist = d
                    best_id = pid

        return best_id

    def update(
        self,
        product_detections: List[Any],
        timestamp: float
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Processes product detections from YOLO.
        Returns:
            - newly_removed_events: list of confirmed POTENTIAL_REMOVAL events
            - returned_events: list of restored PRESENT events
        """
        newly_removed = []
        returned_events = []
        current_seen_ids = set()

        for d in product_detections:
            if d.class_name == "person":
                continue

            x1, y1, x2, y2 = d.bbox
            cx = (x1 + x2) / 2.0
            cy = (y1 + y2) / 2.0
            conf = float(d.confidence)

            # Determine shelf zone
            zone = self.zone_mgr.get_zone_at(cx, cy)
            shelf_id = zone.zone_id if (zone and zone.zone_type == "SHELF_ZONE") else "UNASSIGNED_SHELF"

            sku_id = getattr(d, 'sku_id', None) or d.class_name
            pname = getattr(d, 'product_name', None) or d.class_name

            matched_id = self._match_or_create_product_id(sku_id, shelf_id, (cx, cy))
            if matched_id is None:
                matched_id = f"PROD_{sku_id}_{self.next_item_counter}"
                self.next_item_counter += 1
                self.tracked_products[matched_id] = TrackedProduct(
                    product_id=matched_id,
                    sku_id=sku_id,
                    product_name=pname,
                    shelf_id=shelf_id,
                    bbox=(x1, y1, x2, y2),
                    confidence=conf,
                    timestamp=timestamp
                )

            tp = self.tracked_products[matched_id]
            current_seen_ids.add(matched_id)

            # If this product was previously flagged as POTENTIAL_REMOVAL, it reappeared!
            if tp.current_status == "POTENTIAL_REMOVAL":
                tp.current_status = "PRESENT"
                tp.disappeared_time = None
                returned_events.append({
                    "event_type": "PRODUCT_RETURNED_TO_SHELF",
                    "product_id": tp.product_id,
                    "sku_id": tp.sku_id,
                    "product_name": tp.product_name,
                    "shelf_id": tp.shelf_id,
                    "person_id": tp.associated_person_id,
                    "timestamp": timestamp
                })

            tp.last_seen_time = timestamp
            tp.bbox = (x1, y1, x2, y2)
            tp.confidence = conf

        # Check for disappeared products
        for pid, tp in list(self.tracked_products.items()):
            if pid not in current_seen_ids:
                # Product is missing in this frame
                if tp.disappeared_time is None:
                    tp.disappeared_time = timestamp

                missing_duration = timestamp - tp.disappeared_time

                if tp.current_status == "PRESENT" and missing_duration >= self.missing_seconds_threshold:
                    # Check if a person was actively interacting with this shelf
                    person = self.interaction_tracker.get_person_near_shelf(tp.shelf_id, current_time=timestamp)
                    if person:
                        dwell = person.shelf_dwell_time if person.active_shelf_id == tp.shelf_id else getattr(person, 'last_shelf_dwell_time', person.shelf_dwell_time)
                        if dwell >= self.min_shelf_interaction_sec:
                            tp.current_status = "POTENTIAL_REMOVAL"
                            tp.associated_person_id = person.person_id
                            tp.interaction_verified = True
                        
                        if tp.sku_id not in person.interacted_products:
                            person.interacted_products.append(tp.sku_id)

                        removal_event = {
                            "event_type": "POTENTIAL_PRODUCT_REMOVAL",
                            "product_id": tp.product_id,
                            "sku_id": tp.sku_id,
                            "product_name": tp.product_name,
                            "shelf_id": tp.shelf_id,
                            "person_id": person.person_id,
                            "missing_duration": round(missing_duration, 2),
                            "timestamp": timestamp
                        }
                        person.potential_removals.append(removal_event)
                        newly_removed.append(removal_event)

                # Clean up items missing for more than 5 minutes
                if missing_duration > 300.0:
                    del self.tracked_products[pid]

        return newly_removed, returned_events

    def get_products_by_shelf(self, shelf_id: str) -> List[Dict[str, Any]]:
        return [
            tp.to_dict() for tp in self.tracked_products.values()
            if tp.shelf_id == shelf_id and tp.current_status == "PRESENT"
        ]
