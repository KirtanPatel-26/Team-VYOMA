from collections import defaultdict, deque
from typing import Dict
import statistics

class TemporalSmoother:
    """
    Temporal filter applying a rolling-window median over raw frame-by-frame inventory counts.
    Prevents single-frame customer occlusions or transient detection misses from
    falsely dropping inventory counts and triggering spurious stockout alerts.
    """

    def __init__(self, window_size: int = 7):
        self.window_size = window_size
        self.history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=self.window_size))

    def update(self, raw_counts: Dict[str, int]) -> Dict[str, int]:
        """
        Feed in latest single-frame raw product counts, return temporally smoothed counts.
        """
        smoothed = {}

        # Add observations for products present in this frame
        for product_name, count in raw_counts.items():
            self.history[product_name].append(count)

        # Also handle products previously tracked that may have dropped to 0 in this frame
        for product_name, deq in self.history.items():
            if product_name not in raw_counts:
                deq.append(0)

            # Compute median of history window
            if len(deq) > 0:
                smoothed[product_name] = int(round(statistics.median(deq)))
            else:
                smoothed[product_name] = 0

        return smoothed

    def reset(self):
        """Clear smoothing history."""
        self.history.clear()
