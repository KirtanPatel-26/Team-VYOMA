from collections import Counter


class InventoryCounter:
    def count(self, detections):
        counts = Counter()
        for d in detections:
            if d.product_name:
                counts[d.product_name] += 1
        return dict(counts)
