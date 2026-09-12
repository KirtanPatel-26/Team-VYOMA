import time
import math
from typing import Dict, List, Tuple, Optional, Any
from app.theft.zones import StoreZone, StoreZoneManager

class PersonState:
    """State of a tracked person across store zones and shelves."""
    def __init__(self, person_id: int, initial_pos: Tuple[float, float], initial_time: float):
        self.person_id = person_id
        self.center = initial_pos
        self.bbox: Tuple[int, int, int, int] = (0, 0, 0, 0)
        self.first_seen = initial_time
        self.last_seen = initial_time
        self.current_zone = "Aisle / Common Area"
        self.current_zone_type = "AISLE_ZONE"
        self.previous_zone = "Aisle / Common Area"
        self.zone_entry_time = initial_time
        
        # Shelf interaction tracking
        self.active_shelf_id: Optional[str] = None
        self.shelf_entry_time: Optional[float] = None
        self.shelf_dwell_time: float = 0.0
        self.last_shelf_id: Optional[str] = None
        self.last_shelf_leave_time: Optional[float] = None
        self.last_shelf_dwell_time: float = 0.0
        self.interacted_shelves: List[str] = []
        self.interacted_products: List[str] = [] # list of sku_ids or product names
        
        # Potential removal & risk state
        self.potential_removals: List[Dict[str, Any]] = []
        self.checkout_detected: bool = False
        self.exit_detected: bool = False

    def update_position(
        self,
        center: Tuple[float, float],
        bbox: Tuple[int, int, int, int],
        zone_mgr: StoreZoneManager,
        timestamp: float
    ):
        self.center = center
        self.bbox = bbox
        self.last_seen = timestamp

        new_zone = zone_mgr.get_zone_at(center[0], center[1])
        new_zone_name = new_zone.name if new_zone else "Aisle / Common Area"
        new_zone_type = new_zone.zone_type if new_zone else "AISLE_ZONE"

        if new_zone_name != self.current_zone:
            self.previous_zone = self.current_zone
            self.current_zone = new_zone_name
            self.current_zone_type = new_zone_type
            self.zone_entry_time = timestamp

        # Check shelf interaction
        if new_zone and new_zone.zone_type == "SHELF_ZONE":
            if self.active_shelf_id != new_zone.zone_id:
                self.active_shelf_id = new_zone.zone_id
                self.shelf_entry_time = timestamp
                if new_zone.zone_id not in self.interacted_shelves:
                    self.interacted_shelves.append(new_zone.zone_id)
            self.shelf_dwell_time = timestamp - (self.shelf_entry_time or timestamp)
        else:
            # Check if person is closely hovering near a shelf even if center is slightly outside
            closest_shelf = None
            closest_dist = 65.0 # pixels threshold
            for sz in zone_mgr.get_shelf_zones():
                d = sz.distance_to_point(center[0], center[1])
                if d < closest_dist:
                    closest_dist = d
                    closest_shelf = sz

            if closest_shelf:
                if self.active_shelf_id != closest_shelf.zone_id:
                    self.active_shelf_id = closest_shelf.zone_id
                    self.shelf_entry_time = timestamp
                    if closest_shelf.zone_id not in self.interacted_shelves:
                        self.interacted_shelves.append(closest_shelf.zone_id)
                self.shelf_dwell_time = timestamp - (self.shelf_entry_time or timestamp)
            else:
                if self.active_shelf_id:
                    self.last_shelf_id = self.active_shelf_id
                    self.last_shelf_leave_time = timestamp
                    self.last_shelf_dwell_time = self.shelf_dwell_time
                self.active_shelf_id = None
                self.shelf_dwell_time = 0.0

        # Mark checkout & exit detections
        if self.current_zone_type == "CHECKOUT_ZONE":
            self.checkout_detected = True
        elif self.current_zone_type == "EXIT_ZONE":
            self.exit_detected = True
        else:
            # Check if person's body or foot position is within the exit corridor between Shelf C & Billing Counter
            for ez in zone_mgr.get_exit_zones():
                foot_y = (center[1] + bbox[3]) / 2.0
                if ez.contains_point(center[0], center[1]) or ez.contains_point(center[0], foot_y) or ez.distance_to_point(center[0], center[1]) <= 30.0:
                    self.current_zone = ez.name
                    self.current_zone_type = "EXIT_ZONE"
                    self.exit_detected = True
                    break


class InteractionTracker:
    """
    Monitors spatial and temporal correlations between tracked people and store shelves.
    Detects when a person approaches, dwells, and reaches towards shelf goods.
    """
    def __init__(self, zone_manager: StoreZoneManager):
        self.zone_mgr = zone_manager
        self.persons: Dict[int, PersonState] = {} # person_id -> PersonState
        self.last_update_time: float = 0.0

    def update(self, person_detections: List[Any], timestamp: float) -> Dict[int, PersonState]:
        self.last_update_time = timestamp
        current_ids = set()

        for d in person_detections:
            if d.class_name != "person":
                continue
            pid = d.track_id
            if pid is None:
                continue

            current_ids.add(pid)
            x1, y1, x2, y2 = d.bbox
            cx = (x1 + x2) / 2.0
            cy = (y1 + y2) / 2.0

            if pid not in self.persons:
                self.persons[pid] = PersonState(pid, (cx, cy), timestamp)

            p_state = self.persons[pid]
            p_state.update_position((cx, cy), (x1, y1, x2, y2), self.zone_mgr, timestamp)

        # Cleanup lost tracks (older than 10 seconds of disappearance)
        for pid in list(self.persons.keys()):
            if pid not in current_ids:
                if timestamp - self.persons[pid].last_seen > 10.0:
                    del self.persons[pid]

        return self.persons

    def get_person_near_shelf(self, shelf_zone_id: str, max_age: float = 5.0, current_time: Optional[float] = None) -> Optional[PersonState]:
        """Finds any person currently or recently interacting with the given shelf."""
        now = current_time if current_time is not None else (self.last_update_time if self.last_update_time > 0 else time.time())
        for p in self.persons.values():
            if p.active_shelf_id == shelf_zone_id and (now - p.last_seen) <= max_age:
                return p
            if p.last_shelf_id == shelf_zone_id and p.last_shelf_leave_time and (now - p.last_shelf_leave_time) <= 6.0:
                return p
        return None
