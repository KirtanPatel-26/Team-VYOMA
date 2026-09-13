import os
try:
    import cv2
except ImportError:
    cv2 = None
import time
import uuid
import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any

from app.config.settings import DATA_DIR
from app.theft.config import TheftConfig, get_theft_config
from app.theft.zones import StoreZoneManager
from app.theft.interaction import InteractionTracker, PersonState
from app.theft.product_tracker import ProductRemovalTracker
from app.theft.risk_engine import RiskScoringEngine, RiskLevel

SNAPSHOT_DIR = DATA_DIR / "snapshots"
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

class TheftDetectionEngine:
    """
    AI-assisted Loss Prevention and Suspicious Product-Removal Engine.
    Operates without extra YOLO passes by reusing existing person/product detections and tracker.
    """
    def __init__(
        self,
        camera_id: str = "camera_01",
        local_db = None,
        supabase_db = None
    ):
        self.camera_id = camera_id
        self.local_db = local_db
        self.supabase_db = supabase_db
        self.config = get_theft_config()
        self.zone_mgr = StoreZoneManager(camera_id=camera_id)
        self.interaction_tracker = InteractionTracker(self.zone_mgr)
        self.product_tracker = ProductRemovalTracker(
            self.zone_mgr,
            self.interaction_tracker,
            missing_seconds_threshold=self.config.product_missing_seconds,
            min_shelf_interaction_sec=self.config.min_shelf_interaction_seconds
        )
        self.risk_engine = RiskScoringEngine(self.config)
        
        # In-memory tracking of triggered events to avoid spamming
        self.active_events: Dict[str, Dict[str, Any]] = {} # event_id -> event_dict
        self.triggered_persons: Dict[int, str] = {} # person_id -> event_id
        self.last_high_risk_time: float = 0.0
        self.latest_high_risk_alert: Optional[Dict[str, Any]] = None

    def process_frame(
        self,
        frame: Any,
        recognized_detections: List[Any],
        timestamp: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        Main per-frame processing function called from the background AI pipeline.
        """
        if not self.config.enabled or frame is None:
            return []

        t_now = timestamp or time.time()
        new_incidents = []

        # 1. Update person trajectories & shelf zones
        persons = self.interaction_tracker.update(recognized_detections, t_now)

        # 2. Update product inventory status on shelves & detect potential removals
        newly_removed, returned = self.product_tracker.update(recognized_detections, t_now)

        # 3. Inform risk engine of product disappearance & return events
        for rem in newly_removed:
            self.risk_engine.process_product_removal_event(rem)

        for ret in returned:
            self.risk_engine.process_product_returned_event(ret)

        # 4. Evaluate spatial behavioral trajectory for all active persons
        for pid, p_state in persons.items():
            self.risk_engine.process_person_movement(p_state, t_now)
            profile = self.risk_engine.get_or_create_profile(pid)

            # Check if threshold reached
            if profile.risk_score >= self.config.theft_risk_threshold:
                existing_event_id = self.triggered_persons.get(pid)
                
                if existing_event_id and existing_event_id in self.active_events:
                    # Update live event score & timeline
                    ev = self.active_events[existing_event_id]
                    ev["risk_score"] = profile.risk_score
                    ev["risk_level"] = profile.risk_level.value
                    ev["current_zone"] = p_state.current_zone
                    ev["checkout_detected"] = p_state.checkout_detected
                    ev["timeline"] = [t.to_dict() for t in profile.timeline]
                else:
                    # Create new alert event
                    event_id = f"THEFT_{int(t_now)}_{uuid.uuid4().hex[:6]}"
                    self.triggered_persons[pid] = event_id

                    # Save CCTV frame snapshot as forensic evidence
                    snapshot_filename = f"{event_id}.jpg"
                    snapshot_path = str(SNAPSHOT_DIR / snapshot_filename)
                    try:
                        # Draw evidence box on snapshot image
                        snap_img = frame.copy()
                        bx1, by1, bx2, by2 = p_state.bbox
                        if bx2 > bx1 and by2 > by1:
                            cv2.rectangle(snap_img, (bx1, by1), (bx2, by2), (0, 0, 255), 2)
                            cv2.putText(
                                snap_img, f"Subject #{pid} | Risk: {profile.risk_score}%",
                                (bx1, max(20, by1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2
                            )
                        cv2.imwrite(snapshot_path, snap_img)
                    except Exception as err:
                        print(f"[TheftEngine] Could not save snapshot: {err}")
                        snapshot_filename = ""

                    event_data = {
                        "id": event_id,
                        "event_id": event_id,
                        "camera_id": self.camera_id,
                        "person_id": pid,
                        "product_id": profile.primary_sku_id or "SKU001",
                        "product_name": profile.primary_product_name or "Product",
                        "shelf_id": profile.primary_shelf_id or "SHELF_A",
                        "risk_score": profile.risk_score,
                        "risk_level": profile.risk_level.value,
                        "event_type": "EXIT_WITHOUT_BILLING" if not p_state.checkout_detected and p_state.exit_detected else "POTENTIAL_PRODUCT_REMOVAL",
                        "current_zone": p_state.current_zone,
                        "checkout_detected": p_state.checkout_detected,
                        "snapshot_url": f"/api/theft-events/snapshots/{snapshot_filename}",
                        "snapshot_filename": snapshot_filename,
                        "status": "ACTIVE",
                        "timeline": [t.to_dict() for t in profile.timeline],
                        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                        "resolved_at": None
                    }

                    self.active_events[event_id] = event_data
                    new_incidents.append(event_data)

                    if profile.risk_score >= self.config.high_risk_min:
                        self.last_high_risk_time = t_now
                        self.latest_high_risk_alert = event_data

                    # Persist event to Local SQLite database
                    if self.local_db:
                        try:
                            self.local_db.insert_theft_event(event_data)
                        except Exception as e:
                            print(f"[TheftEngine] SQLite insert error: {e}")

                    # Sync to Supabase if connected
                    if self.supabase_db and self.supabase_db.enabled:
                        try:
                            self.supabase_db.insert_theft_event(event_data)
                        except Exception as e:
                            print(f"[TheftEngine] Supabase insert note: {e}")

        return new_incidents

    def annotate_cctv_frame(self, frame: Any) -> Any:
        """
        Draws visual overlays on the CCTV stream for operator situational awareness:
        - Store zone outlines (Shelf, Checkout, Exit)
        - Warning colored bounding box around persons with elevated risk
        - High-Risk Top Warning Alert Banner
        """
        if frame is None or not self.config.enabled or cv2 is None:
            return frame

        # 1. Draw zones
        for z in self.zone_mgr.zones:
            x1, y1, x2, y2 = z.bbox
            if z.zone_type == "SHELF_ZONE":
                cv2.rectangle(frame, (x1, y1), (x2, y2), (240, 160, 20), 1)
                cv2.putText(frame, f"📦 {z.name}", (x1 + 4, y1 + 16), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (240, 180, 50), 1)
            elif z.zone_type == "CHECKOUT_ZONE":
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 220, 100), 1)
                cv2.putText(frame, "💳 CHECKOUT ZONE", (x1 + 4, y1 + 16), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (0, 220, 100), 1)
            elif z.zone_type == "EXIT_ZONE":
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
                cv2.putText(frame, f"🚪 {z.name}", (x1 + 4, y1 + 18), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 100, 255), 1)

        # 2. Draw warning badges on subjects with elevated risk
        for pid, p_state in self.interaction_tracker.persons.items():
            profile = self.risk_engine.get_or_create_profile(pid)
            if profile.risk_score >= self.config.theft_risk_threshold:
                bx1, by1, bx2, by2 = p_state.bbox
                if bx2 > bx1 and by2 > by1:
                    is_high = profile.risk_score >= self.config.high_risk_min
                    color = (0, 0, 255) if is_high else (0, 140, 255) # Red for HIGH, Amber for SUSPICIOUS
                    
                    # Double rectangle for prominent alert
                    cv2.rectangle(frame, (bx1, by1), (bx2, by2), color, 3 if is_high else 2)
                    
                    badge_title = f"{'🚨 HIGH RISK' if is_high else '⚠️ SUSPICIOUS'}: Person #{pid}"
                    badge_sub = f"Risk: {profile.risk_score}% | {profile.primary_product_name or 'Item'} | {p_state.current_zone}"
                    
                    # Draw label background
                    cv2.rectangle(frame, (bx1, max(0, by1 - 36)), (bx1 + 290, by1), (15, 23, 42), -1)
                    cv2.rectangle(frame, (bx1, max(0, by1 - 36)), (bx1 + 290, by1), color, 1)
                    cv2.putText(frame, badge_title, (bx1 + 5, max(12, by1 - 20)), cv2.FONT_HERSHEY_SIMPLEX, 0.42, color, 1)
                    cv2.putText(frame, badge_sub, (bx1 + 5, max(24, by1 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 255), 1)

        # 3. Top High-Risk Warning Alert Banner (visible for 8 seconds after trigger)
        t_now = time.time()
        if (t_now - self.last_high_risk_time) < 8.0 and self.latest_high_risk_alert:
            alert = self.latest_high_risk_alert
            # Top Banner
            cv2.rectangle(frame, (0, 0), (1280, 42), (0, 0, 180), -1)
            cv2.rectangle(frame, (0, 0), (1280, 42), (0, 0, 255), 2)
            if alert.get("event_type") == "EXIT_WITHOUT_BILLING":
                banner_text = (
                    f"🚨 THEFT ALERT: Person #{alert['person_id']} (Risk: {alert['risk_score']}%) - "
                    f"EXITED WITHOUT BILLING via Shelf C Corridor! [STAFF VERIFICATION REQUIRED]"
                )
            else:
                banner_text = (
                    f"🚨 SUSPICIOUS ACTIVITY ALERT: Person #{alert['person_id']} (Risk: {alert['risk_score']}%) - "
                    f"Potential {alert['product_name']} Removal near {alert['shelf_id']} -> Zone: {alert['current_zone']} [HUMAN VERIFICATION REQUIRED]"
                )
            cv2.putText(frame, banner_text, (20, 26), cv2.FONT_HERSHEY_DUPLEX, 0.46, (255, 255, 255), 1)

        return frame

    def simulate_demo_event(self, frame: Optional[Any] = None) -> Dict[str, Any]:
        """
        Generates a realistic end-to-end demo scenario for hackathon demonstration.
        Follows the exact specified sequence:
        Shopper enters shelf zone -> interacts with shelf -> product disappears ->
        shopper moves toward exit -> no checkout detected -> HIGH-RISK alert appears!
        """
        t_now = time.time()
        event_id = f"DEMO_THEFT_{int(t_now)}"
        sim_person_id = 17

        # Base snapshot creation
        snapshot_filename = f"{event_id}.jpg"
        snapshot_path = str(SNAPSHOT_DIR / snapshot_filename)
        
        if cv2 is not None:
            if frame is not None:
                snap_img = frame.copy()
                # Draw synthetic suspect box on demo frame (near exit or shelf)
                cv2.rectangle(snap_img, (1160, 220), (1260, 480), (0, 0, 255), 2)
                cv2.putText(snap_img, "Subject #17 | Risk: 87%", (1160, 210), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
                cv2.imwrite(snapshot_path, snap_img)
            else:
                try:
                    import numpy as np
                    canvas = np.zeros((720, 1280, 3), dtype=np.uint8)
                    canvas[:] = (20, 28, 44)
                    cv2.putText(canvas, "SmartRetail AI - Loss Prevention Evidence Frame", (40, 60), cv2.FONT_HERSHEY_DUPLEX, 0.8, (56, 189, 248), 2)
                    cv2.rectangle(canvas, (900, 200), (1150, 600), (0, 0, 255), 2)
                    cv2.putText(canvas, "Person #17 (Risk: 87%)", (900, 190), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
                    cv2.imwrite(snapshot_path, canvas)
                except Exception:
                    pass

        # Build chronological timeline with realistic human timestamps
        t_base = t_now - 26.0
        timeline = [
            {
                "timestamp": time.strftime("%H:%M:%S", time.localtime(t_base)),
                "description": "Shopper entered and interacted with shelf SHELF_C (Dairy & Essentials)",
                "score_delta": "+20",
                "current_score": 20
            },
            {
                "timestamp": time.strftime("%H:%M:%S", time.localtime(t_base + 3)),
                "description": "Item 'Amul Taaza (Milk SKU004)' disappeared from shelf after interaction",
                "score_delta": "+25",
                "current_score": 45
            },
            {
                "timestamp": time.strftime("%H:%M:%S", time.localtime(t_base + 7)),
                "description": "Shopper walked away from shelf area carrying potential item",
                "score_delta": "+15",
                "current_score": 60
            },
            {
                "timestamp": time.strftime("%H:%M:%S", time.localtime(t_base + 15)),
                "description": "Shopper reached store exit zone without passing checkout counter",
                "score_delta": "+30",
                "current_score": 87
            },
            {
                "timestamp": time.strftime("%H:%M:%S", time.localtime(t_base + 22)),
                "description": "🚨 HIGH-RISK ALERT: Potential theft / suspicious product-removal activity (Staff verification dispatched)",
                "score_delta": "+0",
                "current_score": 87
            }
        ]

        demo_event = {
            "id": event_id,
            "event_id": event_id,
            "camera_id": self.camera_id,
            "person_id": sim_person_id,
            "product_id": "SKU004",
            "product_name": "Amul Taaza (Milk)",
            "shelf_id": "SHELF_C (Dairy)",
            "risk_score": 87,
            "risk_level": "HIGH",
            "event_type": "POTENTIAL_PRODUCT_REMOVAL",
            "current_zone": "EXIT",
            "checkout_detected": False,
            "snapshot_url": f"/api/theft-events/snapshots/{snapshot_filename}",
            "snapshot_filename": snapshot_filename,
            "status": "ACTIVE",
            "timeline": timeline,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "resolved_at": None
        }

        self.active_events[event_id] = demo_event
        self.last_high_risk_time = t_now
        self.latest_high_risk_alert = demo_event

        # Save to SQLite
        if self.local_db:
            try:
                self.local_db.insert_theft_event(demo_event)
            except Exception as e:
                print(f"[TheftEngine] Demo SQLite error: {e}")

        # Save to Supabase if connected
        if self.supabase_db and self.supabase_db.enabled:
            try:
                self.supabase_db.insert_theft_event(demo_event)
            except Exception as e:
                print(f"[TheftEngine] Demo Supabase error: {e}")

        return demo_event

    def update_event_status(self, event_id: str, new_status: str) -> bool:
        """Updates event status: ACTIVE, UNDER_REVIEW, RESOLVED, FALSE_POSITIVE."""
        if event_id in self.active_events:
            self.active_events[event_id]["status"] = new_status
            if new_status in ("RESOLVED", "FALSE_POSITIVE"):
                self.active_events[event_id]["resolved_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")

        if self.local_db:
            return self.local_db.update_theft_event_status(event_id, new_status)
        return True

    def reset_cycle(self):
        """
        Resets transient tracking state when the demo video loops back to start,
        allowing the theft scenario to trigger and demonstrate again without wiping persistent DB events.
        """
        self.interaction_tracker.persons.clear()
        self.product_tracker.tracked_products.clear()
        self.risk_engine.profiles.clear()
        self.triggered_persons.clear()
        self.latest_high_risk_alert = None
        self.last_high_risk_time = 0.0

