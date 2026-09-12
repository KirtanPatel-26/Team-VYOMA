"""
SmartRetail AI - Enhanced Planogram & Shelf Compliance Auditor
=============================================================
Audits shelf layout against POS planograms:
- Identifies misplaced products with exact origin and destination shelf bays
- Emits prescriptive "MOVE PRODUCT" staff instructions
- Measures shelf void percentage and facing compliance
"""

from typing import List, Dict, Any

class ShelfAnalytics:
    def __init__(self):
        # Master zone-to-expected products map
        self.zone_catalog = {
            "Beverages & Juices": ["Fanta Orange", "Real Orange Juice", "Coca Cola"],
            "Snacks & Biscuits": ["Pringles Original", "Oreo", "Lays Classic", "Dairy Milk"],
            "Dairy & Essentials": ["Amul Taaza", "Dove Soap", "Colgate Paste"]
        }

    def analyze(self, detections, shelf_zones=None) -> Dict[str, Any]:
        shelf_zones = shelf_zones or []
        results = []
        total_slots = max(1, len(shelf_zones))
        compliant_slots = 0
        planogram_violations = []

        for zone in shelf_zones:
            zx1, zy1, zx2, zy2 = zone["bbox"]
            zone_name = zone.get("name", "")
            expected_names = zone.get("expected_names") or self.zone_catalog.get(zone_name, [])

            detected_products = []
            misplaced_products = []

            for d in detections:
                if d.class_name == "person":
                    continue
                x1, y1, x2, y2 = d.bbox
                cx = (x1 + x2) / 2.0
                cy = (y1 + y2) / 2.0

                if zx1 <= cx <= zx2 and zy1 <= cy <= zy2:
                    pname = d.product_name or d.class_name
                    detected_products.append(pname)
                    if expected_names and pname not in expected_names and pname != "Unknown / Low Confidence":
                        misplaced_products.append(pname)

            detected_count = len(detected_products)
            unique_detected = list(set(detected_products))

            # Determine compliance status
            if detected_count == 0:
                status = "EMPTY_SLOT"
                compliance = 0
                planogram_violations.append({
                    "type": "SHELF_VOID",
                    "zone": zone_name,
                    "shelf_code": zone.get("shelf_code", "SHELF"),
                    "severity": "HIGH",
                    "details": f"Complete shelf gap in {zone_name}. Zero units detected.",
                    "action": f"Restock {zone_name} from back-room inventory"
                })
            elif misplaced_products:
                status = "MISPLACED_ITEMS"
                compliance = 50
                for mp in set(misplaced_products):
                    correct_zone = "Unknown Zone"
                    for zname, expected in self.zone_catalog.items():
                        if mp in expected:
                            correct_zone = zname
                            break
                    planogram_violations.append({
                        "type": "MISPLACED_SKU",
                        "zone": zone_name,
                        "shelf_code": zone.get("shelf_code", "SHELF"),
                        "severity": "MODERATE",
                        "product": mp,
                        "current_zone": zone_name,
                        "correct_zone": correct_zone,
                        "details": f"Misplaced item '{mp}' detected in '{zone_name}'. Expected in '{correct_zone}'.",
                        "action": f"MOVE PRODUCT: Relocate '{mp}' from {zone_name} to {correct_zone}"
                    })
            else:
                status = "COMPLIANT"
                compliance = 100
                compliant_slots += 1

            results.append({
                "zone": zone_name,
                "shelf_code": zone.get("shelf_code", "SHELF"),
                "category": zone.get("category", "General"),
                "detected_count": detected_count,
                "detected_items": unique_detected,
                "expected_items": expected_names,
                "misplaced_items": list(set(misplaced_products)),
                "compliance_score": compliance,
                "status": status
            })

        overall_compliance = round((compliant_slots / total_slots) * 100.0, 1)

        return {
            "overall_compliance_score": overall_compliance,
            "shelves": results,
            "planogram_violations": planogram_violations,
            "total_violations": len(planogram_violations)
        }
