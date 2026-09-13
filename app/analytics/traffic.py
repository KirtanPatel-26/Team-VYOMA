import time
try:
    import numpy as np
except ImportError:
    np = None
from collections import defaultdict, deque

class TrafficAnalytics:
    """
    Real-time anonymous shopper & staff traffic analysis:
    - Footfall counting (In / Out / Current Occupancy)
    - Staff vs Customer AI distinction & Staffing Ratio
    - Zone dwell times & customer engagement
    - Customer Journey tracking (zone progression path)
    - Zone conversion & behavioral engagement intelligence
    - 2D store movement heatmap matrix
    """
    def __init__(self, zones=None, entrance_zone=None, exit_zone=None):
        self.zones = zones or []
        self.entrance_zone = entrance_zone or [0, 200, 120, 720]
        self.exit_zone = exit_zone or [1160, 200, 1280, 720]
        
        # Virtual Directional Tripwire lines
        self.tripwire_in_x = 140
        self.tripwire_out_x = 1140
        self.tripwire_in_crossings = 0
        self.tripwire_out_crossings = 0
        self.prev_positions = {} # track_id -> (prev_x, prev_y)

        self.seen_ids = set()
        self.active_persons = {} # track_id -> {"pos": (x,y), "zone": str, "zone_sequence": list, ...}
        self.completed_journeys = deque(maxlen=25) # list of completed customer paths
        self.total_in = 0
        self.total_out = 0
        self.dwell_history = []
        self.zone_dwell_accum = defaultdict(float)
        self.zone_visit_counts = defaultdict(int)
        
        # Promotional display engagement
        self.promotional_dwell_accum = defaultdict(float)
        self.promotional_engagements = defaultdict(int)

        # Spatial heatmap density grid (36 x 20 resolution = 720 cells)
        self.grid_cols = 36
        self.grid_rows = 20
        if np is not None:
            self.heatmap_grid = np.zeros((self.grid_rows, self.grid_cols), dtype=np.float32)
        else:
            self.heatmap_grid = [[0.0 for _ in range(self.grid_cols)] for _ in range(self.grid_rows)]

    def _get_zone_name(self, cx, cy):
        for z in self.zones:
            zx1, zy1, zx2, zy2 = z["bbox"]
            if zx1 <= cx <= zx2 and zy1 <= cy <= zy2:
                return z["name"]
        return "Aisle / Common Area"

    def update(self, detections):
        current_time = time.time()
        persons = [d for d in detections if d.class_name == "person"]
        
        # Differentiate Staff vs Customers
        customers = [d for d in persons if getattr(d, 'person_type', 'customer') == 'customer']
        staff = [d for d in persons if getattr(d, 'person_type', 'customer') == 'staff']
        
        current_frame_ids = set()

        for d in customers:
            tid = d.track_id
            if tid is None:
                continue

            current_frame_ids.add(tid)
            x1, y1, x2, y2 = d.bbox
            cx = (x1 + x2) / 2.0
            cy = (y1 + y2) / 2.0

            # Update heatmap grid density
            gx = int(min(self.grid_cols - 1, max(0, (cx / 1280.0) * self.grid_cols)))
            gy = int(min(self.grid_rows - 1, max(0, (cy / 720.0) * self.grid_rows)))
            if np is not None and isinstance(self.heatmap_grid, np.ndarray):
                self.heatmap_grid[gy, gx] += 1.0
            else:
                self.heatmap_grid[gy][gx] += 1.0

            curr_zone = self._get_zone_name(cx, cy)

            # Virtual Tripwire Line Crossing Logic (Entrance X=140, Exit X=1140)
            prev_pos = self.prev_positions.get(tid)
            if prev_pos is not None:
                px, py = prev_pos
                if px < self.tripwire_in_x <= cx:
                    self.tripwire_in_crossings += 1
                elif px < self.tripwire_out_x <= cx or (px <= self.tripwire_out_x and cx > self.tripwire_out_x):
                    self.tripwire_out_crossings += 1
            self.prev_positions[tid] = (cx, cy)

            # Promotional Display / Feature End-Cap Dwell Tracking
            is_promotional = any(kw in curr_zone.lower() for kw in ["promo", "display", "feature", "end-cap"])

            if tid not in self.seen_ids:
                self.seen_ids.add(tid)
                self.total_in += 1
                self.zone_visit_counts[curr_zone] += 1
                if is_promotional:
                    self.promotional_engagements[curr_zone] += 1
                self.active_persons[tid] = {
                    "pos": (cx, cy),
                    "zone": curr_zone,
                    "zone_sequence": [curr_zone],
                    "first_seen": current_time,
                    "zone_start": current_time,
                    "zone_dwells": defaultdict(float)
                }
            else:
                p = self.active_persons.get(tid)
                if p:
                    if p["zone"] != curr_zone:
                        dwell = current_time - p["zone_start"]
                        p["zone_dwells"][p["zone"]] += dwell
                        self.zone_dwell_accum[p["zone"]] += dwell
                        if any(kw in p["zone"].lower() for kw in ["promo", "display", "feature", "end-cap"]):
                            self.promotional_dwell_accum[p["zone"]] += dwell

                        p["zone"] = curr_zone
                        p["zone_start"] = current_time
                        if not p["zone_sequence"] or p["zone_sequence"][-1] != curr_zone:
                            p["zone_sequence"].append(curr_zone)
                            self.zone_visit_counts[curr_zone] += 1
                            if is_promotional:
                                self.promotional_engagements[curr_zone] += 1
                    p["pos"] = (cx, cy)

        # Detect shoppers who left the camera view
        active_ids = list(self.active_persons.keys())
        for aid in active_ids:
            if aid not in current_frame_ids:
                p = self.active_persons[aid]
                total_shopper_dwell = current_time - p["first_seen"]
                dwell = current_time - p["zone_start"]
                self.zone_dwell_accum[p["zone"]] += dwell
                self.dwell_history.append(total_shopper_dwell)
                self.total_out += 1
                
                # Record completed customer journey
                clean_path = [z for z in p["zone_sequence"] if z != "Aisle / Common Area"] or p["zone_sequence"]
                self.completed_journeys.append({
                    "track_id": aid,
                    "journey_path": clean_path,
                    "total_dwell_seconds": round(total_shopper_dwell, 1),
                    "exit_time": time.strftime("%H:%M:%S")
                })
                del self.active_persons[aid]

        if self.dwell_history:
            avg_dwell = sum(self.dwell_history) / len(self.dwell_history)
        else:
            avg_dwell = 45.0

        if np is not None and isinstance(self.heatmap_grid, np.ndarray):
            max_heat = max(1.0, float(np.max(self.heatmap_grid)))
            normalized_heat = (self.heatmap_grid / max_heat).tolist()
        else:
            flat = [val for row in self.heatmap_grid for val in row]
            max_heat = max(1.0, max(flat) if flat else 1.0)
            normalized_heat = [[round(val / max_heat, 3) for val in row] for row in self.heatmap_grid]

        staff_count = len(staff)
        customer_count = len(customers)
        ratio = round(customer_count / max(1, staff_count), 1)

        # Staff roles list
        staff_roles = [d.staff_role or "Floor Staff" for d in staff]

        # Anonymized normalized active person tracks for 3D/floor-plan digital twin
        active_tracks = []
        for d in persons:
            bx1, by1, bx2, by2 = d.bbox
            bcx = (bx1 + bx2) / 2.0
            bcy = (by1 + by2) / 2.0
            ptype = getattr(d, 'person_type', 'customer') or 'customer'
            srole = getattr(d, 'staff_role', None)
            active_tracks.append({
                "track_id": d.track_id,
                "x": round(bcx / 1280.0, 4),
                "y": round(bcy / 720.0, 4),
                "type": ptype,
                "role": srole
            })

        # Zone Engagement & Conversion Opportunity Insights
        top_zone = "Aisles"
        if self.zone_visit_counts:
            top_zone = max(self.zone_visit_counts.items(), key=lambda x: x[1])[0]

        engagement_insights = [
            {
                "insight": f"Top visited zone is '{top_zone}' with {self.zone_visit_counts.get(top_zone, 0)} engagements.",
                "type": "TRAFFIC_FLOW"
            }
        ]
        
        # Check high dwell zone
        if self.zone_dwell_accum:
            highest_dwell_zone = max(self.zone_dwell_accum.items(), key=lambda x: x[1])[0]
            if highest_dwell_zone != "Aisle / Common Area":
                engagement_insights.append({
                    "insight": f"'{highest_dwell_zone}' has the highest customer dwell time ({round(self.zone_dwell_accum[highest_dwell_zone], 0)}s). High conversion opportunity for cross-merchandising.",
                    "type": "OPPORTUNITY"
                })

        return {
            "current_people": len(persons),
            "current_customers": customer_count,
            "current_staff": staff_count,
            "staff_roles": staff_roles,
            "customer_to_staff_ratio": f"{ratio} : 1",
            "total_in": self.total_in,
            "total_out": self.total_out,
            "tripwire_in_count": max(self.tripwire_in_crossings, self.total_in),
            "tripwire_out_count": max(self.tripwire_out_crossings, self.total_out),
            "promotional_dwell_summary": {k: round(v, 1) for k, v in self.promotional_dwell_accum.items()},
            "promotional_engagements": dict(self.promotional_engagements),
            "unique_people_seen": len(self.seen_ids),
            "avg_dwell_time": round(avg_dwell, 1),
            "zone_dwell_summary": {k: round(v, 1) for k, v in self.zone_dwell_accum.items()},
            "zone_visit_counts": dict(self.zone_visit_counts),
            "heatmap_grid": normalized_heat,
            "grid_dimensions": {"rows": self.grid_rows, "cols": self.grid_cols},
            "active_tracks": active_tracks,
            "recent_customer_journeys": list(self.completed_journeys)[-6:],
            "engagement_insights": engagement_insights
        }
