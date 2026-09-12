"""
Proactive Queue Analytics & Predictive Congestion Manager
=========================================================
- Real-time queue length measurement and counter utilization
- Predictive congestion forecasting (anticipates long lines 5 minutes ahead)
- Empirical service time and wait time measurement from shopper track lifespans
- Proactive staff dispatch recommendations before customer experience degrades
"""

import time
from collections import deque
from typing import List, Dict, Any, Optional

class QueueAnalytics:
    def __init__(self, queue_zone=None, threshold=4, avg_service_time_sec=45.0):
        self.queue_zone = queue_zone or [850, 380, 1240, 680]
        self.threshold = threshold
        self.default_service_time_sec = avg_service_time_sec
        self.active_counters = 1
        
        # Empirical timing tracking: track_id -> entry_timestamp
        self.queue_entries = {}
        self.completed_wait_times = deque(maxlen=40)
        
        # Rolling arrival rate tracking: list of (timestamp, count)
        self.history = deque(maxlen=30)
        self.arrivals_window = deque(maxlen=50) # timestamps of customer arrivals into queue

    def update(self, detections: List[Any], store_traffic_influx: Optional[float] = None) -> Dict[str, Any]:
        current_time = time.time()
        
        if not self.queue_zone:
            return {
                "queue_length": 0,
                "active_counters": self.active_counters,
                "estimated_wait_time_sec": 0,
                "estimated_wait_time_min": 0,
                "congestion": False,
                "predictive_congestion": False,
                "predicted_queue_5min": 0,
                "empirical_avg_service_sec": self.default_service_time_sec,
                "arrival_rate_per_min": 0.0,
                "recommendation": "All counters operating normally."
            }

        zx1, zy1, zx2, zy2 = self.queue_zone
        count = 0
        current_queue_ids = set()

        for d in detections:
            if d.class_name != "person":
                continue
            x1, y1, x2, y2 = d.bbox
            cx = (x1 + x2) / 2.0
            cy = (y1 + y2) / 2.0

            if zx1 <= cx <= zx2 and zy1 <= cy <= zy2:
                count += 1
                tid = getattr(d, "track_id", None)
                if tid is not None:
                    current_queue_ids.add(tid)
                    if tid not in self.queue_entries:
                        self.queue_entries[tid] = current_time
                        self.arrivals_window.append(current_time)

        # Measure completed empirical wait times for people who departed the queue
        for tid in list(self.queue_entries.keys()):
            if tid not in current_queue_ids:
                entry_t = self.queue_entries.pop(tid)
                dur = current_time - entry_t
                if 2.0 <= dur <= 600.0: # filter noise / pass-throughs
                    self.completed_wait_times.append(dur)

        # Calculate empirical average service time
        if len(self.completed_wait_times) >= 3:
            empirical_service_time = sum(self.completed_wait_times) / len(self.completed_wait_times)
        else:
            empirical_service_time = self.default_service_time_sec

        # Record history snapshot
        self.history.append((current_time, count))

        # Calculate arrival rate (customers per minute)
        cutoff_1m = current_time - 60.0
        recent_arrivals = [t for t in self.arrivals_window if t >= cutoff_1m]
        arrival_rate_per_min = len(recent_arrivals)

        # Fallback to realistic arrival rate if arrivals window is fresh
        if arrival_rate_per_min == 0 and count > 0:
            arrival_rate_per_min = round(count * 0.8, 1)

        # Service departure capacity per minute
        service_capacity_per_min = (60.0 / max(15.0, empirical_service_time)) * self.active_counters

        # ================= PROACTIVE CONGESTION FORECAST (5 MINS AHEAD) =================
        net_growth_per_min = arrival_rate_per_min - service_capacity_per_min
        # Traffic influx multiplier if store has rising civilian footfall
        if store_traffic_influx and store_traffic_influx > 10:
            net_growth_per_min += (store_traffic_influx / 100.0) * 1.2

        predicted_queue_5min = max(0.0, count + (net_growth_per_min * 5.0))
        is_predictive_congested = (predicted_queue_5min >= self.threshold) and (count < self.threshold)
        is_congested = count >= self.threshold

        estimated_wait_sec = (count * empirical_service_time) / max(1, self.active_counters)
        estimated_wait_min = round(estimated_wait_sec / 60.0, 1)

        # Actionable prescriptive recommendation
        if is_congested:
            needed_counters = max(2, (count + 2) // 3)
            rec = f"🚨 High congestion ({count} in line). Recommend opening Billing Counter {needed_counters} immediately to cut wait time to {round(estimated_wait_min / needed_counters, 1)}m."
        elif is_predictive_congested:
            rec = f"⚠️ PROACTIVE ALERT: High influx detected ({arrival_rate_per_min:.1f} arrivals/min). Queue predicted to reach {int(predicted_queue_5min)} in 5 mins. Pre-alert Counter 2."
        elif count >= 3:
            rec = f"Moderate queue ({count} customers). Monitoring checkout rate."
        else:
            rec = "Queue flow is optimal. 1 Active Billing Counter sufficient."

        return {
            "queue_length": count,
            "active_counters": self.active_counters,
            "estimated_wait_time_sec": round(estimated_wait_sec, 1),
            "estimated_wait_time_min": estimated_wait_min,
            "empirical_avg_service_sec": round(empirical_service_time, 1),
            "arrival_rate_per_min": round(arrival_rate_per_min, 1),
            "predicted_queue_5min": round(predicted_queue_5min, 1),
            "predictive_congestion": is_predictive_congested,
            "congestion": is_congested,
            "threshold": self.threshold,
            "recommendation": rec
        }
