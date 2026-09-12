from typing import List, Tuple, Dict, Any
from app.detection.results import Detection

class SpatialShelfFilter:
    """
    Spatial Shelf-ROI filtering and IoU de-duplication utilities for retail environments.
    """

    @staticmethod
    def is_box_inside_zone(box: Tuple[int, int, int, int], zone_bbox: Tuple[int, int, int, int], threshold: float = 0.5) -> bool:
        """Calculate if bbox center or substantial area resides within zone bbox."""
        bx1, by1, bx2, by2 = box
        zx1, zy1, zx2, zy2 = zone_bbox

        cx = (bx1 + bx2) / 2.0
        cy = (by1 + by2) / 2.0

        if zx1 <= cx <= zx2 and zy1 <= cy <= zy2:
            return True

        # Calculate intersection over box area
        ix1 = max(bx1, zx1)
        iy1 = max(by1, zy1)
        ix2 = min(bx2, zx2)
        iy2 = min(by2, zy2)

        if ix2 > ix1 and iy2 > iy1:
            inter_area = (ix2 - ix1) * (iy2 - iy1)
            box_area = (bx2 - bx1) * (by2 - by1)
            if box_area > 0 and (inter_area / box_area) >= threshold:
                return True

        return False

    @classmethod
    def filter_by_shelves(cls, detections: List[Detection], shelf_zones: List[Dict[str, Any]]) -> List[Detection]:
        """Keep only product detections that reside within valid shelf zones."""
        if not shelf_zones:
            return detections

        filtered = []
        for d in detections:
            if d.class_name == "person":
                filtered.append(d)
                continue

            # Check if inside any shelf zone
            in_shelf = False
            for zone in shelf_zones:
                if cls.is_box_inside_zone(d.bbox, zone.get("bbox", [0, 0, 0, 0])):
                    in_shelf = True
                    break

            if in_shelf:
                filtered.append(d)

        return filtered
