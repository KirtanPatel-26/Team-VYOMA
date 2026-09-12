import math
import time
from collections import defaultdict

class CentroidTracker:
    """
    Robust edge tracker with persistent IDs, trajectory history,
    dwell time calculation, and privacy-preserving anonymous identity tracking.
    """

    def __init__(self, max_distance=90, max_missing=15):
        self.max_distance = max_distance
        self.max_missing = max_missing
        self.next_id = 101
        self.objects = {} # id -> {"center": (x,y), "class_name": str, "first_seen": float, "last_seen": float, "zone": str}
        self.missing = {} # id -> int
        self.trajectories = defaultdict(list) # id -> list of (x,y)
        self.dwell_times = defaultdict(float) # id -> seconds

    @staticmethod
    def _center(bbox):
        x1, y1, x2, y2 = bbox
        return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)

    def update(self, detections, shelf_zones=None):
        current_time = time.time()
        current_centers = [self._center(d.bbox) for d in detections]
        used = set()

        for i, detection in enumerate(detections):
            best_id = None
            best_distance = self.max_distance

            for object_id, info in self.objects.items():
                if object_id in used:
                    continue
                if info["class_name"] != detection.class_name:
                    continue

                distance = math.dist(current_centers[i], info["center"])
                if distance < best_distance:
                    best_distance = distance
                    best_id = object_id

            if best_id is None:
                best_id = self.next_id
                self.next_id += 1
                self.objects[best_id] = {
                    "center": current_centers[i],
                    "class_name": detection.class_name,
                    "first_seen": current_time,
                    "last_seen": current_time,
                }
            else:
                self.objects[best_id]["center"] = current_centers[i]
                self.objects[best_id]["last_seen"] = current_time

            detection.track_id = best_id
            self.missing[best_id] = 0
            used.add(best_id)

            # Record trajectory
            cx, cy = int(current_centers[i][0]), int(current_centers[i][1])
            self.trajectories[best_id].append((cx, cy))
            if len(self.trajectories[best_id]) > 40:
                self.trajectories[best_id].pop(0)

            # Calculate dwell time
            first_seen = self.objects[best_id]["first_seen"]
            self.dwell_times[best_id] = current_time - first_seen

        # Handle disappeared objects
        for object_id in list(self.objects):
            if object_id not in used:
                self.missing[object_id] = self.missing.get(object_id, 0) + 1
                if self.missing[object_id] > self.max_missing:
                    del self.objects[object_id]
                    del self.missing[object_id]
                    if object_id in self.trajectories:
                        del self.trajectories[object_id]

        return detections

    def get_trajectories(self):
        return dict(self.trajectories)

    def get_dwell_time(self, object_id):
        return self.dwell_times.get(object_id, 0.0)

    def reset(self):
        self.objects.clear()
        self.missing.clear()
        self.trajectories.clear()
        self.dwell_times.clear()
        self.next_id = 101

