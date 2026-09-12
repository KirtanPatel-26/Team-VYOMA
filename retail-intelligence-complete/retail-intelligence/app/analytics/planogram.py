from typing import List, Dict, Any, Optional
import math

class PlanogramAuditor:
    """
    Slot-level Planogram Auditor.
    Evaluates exact shelf-facing placement against master store planogram.
    
    Statuses per slot:
    - COMPLIANT: Expected SKU is in its assigned physical slot.
    - MISPLACED: A different valid product is encroaching on or placed in this slot.
    - EMPTY: No product detected in this assigned slot.
    - UNEXPECTED_ITEM: Foreign/unknown object detected.
    """

    def __init__(self, shelves_config: Optional[Dict[str, Any]] = None):
        self.shelves_config = shelves_config or {}
        self.zones = self.shelves_config.get("zones", [])

    def update_config(self, shelves_config: Dict[str, Any]):
        self.shelves_config = shelves_config
        self.zones = shelves_config.get("zones", [])

    def audit(self, detections: List[Any], zones: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """
        Audits product detections against configured shelf slots.
        """
        active_zones = zones if zones is not None else self.zones
        
        # Filter only product detections (exclude persons)
        product_detections = [
            d for d in detections
            if getattr(d, "class_name", "") != "person"
        ]

        total_slots_count = 0
        compliant_slots_count = 0
        misplaced_slots_count = 0
        empty_slots_count = 0
        unexpected_slots_count = 0
        violations = []
        zone_audits = []

        for zone in active_zones:
            zone_name = zone.get("name", "Unknown Shelf")
            shelf_code = zone.get("shelf_code", "SHELF")
            z_bbox = zone.get("bbox", [0, 0, 1280, 720])
            slots = zone.get("slots", [])

            # Filter product detections inside this shelf zone
            zone_products = []
            for d in product_detections:
                bx = d.bbox
                cx = (bx[0] + bx[2]) / 2.0
                cy = (bx[1] + bx[3]) / 2.0
                if z_bbox[0] <= cx <= z_bbox[2] and z_bbox[1] <= cy <= z_bbox[3]:
                    prod_name = getattr(d, "product_name", None) or d.class_name
                    sku_id = getattr(d, "sku_id", None) or ""
                    zone_products.append({
                        "detection": d,
                        "cx": cx,
                        "cy": cy,
                        "product_name": prod_name,
                        "sku_id": sku_id,
                        "confidence": float(getattr(d, "confidence", 0.9))
                    })

            slot_results = []
            zone_compliant = 0

            for slot in slots:
                total_slots_count += 1
                pos = slot.get("position", 1)
                s_bbox = slot.get("bbox", z_bbox)
                exp_sku = slot.get("expected_sku", "")
                exp_name = slot.get("expected_name", "")

                # Find all products inside this slot bbox
                matching_prods = []
                for p in zone_products:
                    if s_bbox[0] <= p["cx"] <= s_bbox[2] and s_bbox[1] <= p["cy"] <= s_bbox[3]:
                        matching_prods.append(p)

                # If none directly inside, find the closest product center
                if not matching_prods and zone_products:
                    slot_cx = (s_bbox[0] + s_bbox[2]) / 2.0
                    slot_cy = (s_bbox[1] + s_bbox[3]) / 2.0
                    closest = min(
                        zone_products,
                        key=lambda p: math.hypot(p["cx"] - slot_cx, p["cy"] - slot_cy)
                    )
                    dist = math.hypot(closest["cx"] - slot_cx, closest["cy"] - slot_cy)
                    # Only match if within 70 pixels of slot boundary
                    if dist <= 70:
                        matching_prods.append(closest)

                if not matching_prods:
                    status = "EMPTY"
                    empty_slots_count += 1
                    detected_name = None
                    detected_sku = None
                    conf = 0.0
                    violations.append({
                        "severity": "WARNING",
                        "zone": zone_name,
                        "shelf_code": shelf_code,
                        "position": pos,
                        "status": "EMPTY",
                        "message": f"Position {pos} in '{zone_name}' is EMPTY (Expected: {exp_name}).",
                        "expected_sku": exp_sku,
                        "expected_name": exp_name,
                        "detected_name": None
                    })
                else:
                    # Pick best detected item in slot
                    best_match = matching_prods[0]
                    detected_name = best_match["product_name"]
                    detected_sku = best_match["sku_id"]
                    conf = best_match["confidence"]

                    # Check compliance against expected SKU or Name
                    name_matches = (
                        exp_name.lower() in detected_name.lower() or
                        detected_name.lower() in exp_name.lower()
                    )
                    sku_matches = (exp_sku and exp_sku == detected_sku)

                    if name_matches or sku_matches:
                        status = "COMPLIANT"
                        compliant_slots_count += 1
                        zone_compliant += 1
                    elif "unknown" in detected_name.lower() or conf < 0.4:
                        status = "UNEXPECTED_ITEM"
                        unexpected_slots_count += 1
                        violations.append({
                            "severity": "WARNING",
                            "zone": zone_name,
                            "shelf_code": shelf_code,
                            "position": pos,
                            "status": "UNEXPECTED_ITEM",
                            "message": f"Position {pos} in '{zone_name}' has unrecognized item (Expected: {exp_name}).",
                            "expected_sku": exp_sku,
                            "expected_name": exp_name,
                            "detected_name": detected_name
                        })
                    else:
                        status = "MISPLACED"
                        misplaced_slots_count += 1
                        violations.append({
                            "severity": "CRITICAL",
                            "zone": zone_name,
                            "shelf_code": shelf_code,
                            "position": pos,
                            "status": "MISPLACED",
                            "message": f"Position {pos} in '{zone_name}' should have {exp_name} — {detected_name} detected instead.",
                            "expected_sku": exp_sku,
                            "expected_name": exp_name,
                            "detected_name": detected_name
                        })

                slot_results.append({
                    "position": pos,
                    "expected_sku": exp_sku,
                    "expected_name": exp_name,
                    "detected_sku": detected_sku,
                    "detected_name": detected_name,
                    "confidence": round(conf, 2),
                    "status": status,
                    "bbox": s_bbox
                })

            total_zone_slots = max(1, len(slots))
            zone_score = round((zone_compliant / total_zone_slots) * 100.0, 1)

            zone_audits.append({
                "zone_name": zone_name,
                "shelf_code": shelf_code,
                "total_slots": len(slots),
                "compliant_slots": zone_compliant,
                "compliance_score": zone_score,
                "slots": slot_results
            })

        overall_score = (
            round((compliant_slots_count / max(1, total_slots_count)) * 100.0, 1)
            if total_slots_count > 0 else 100.0
        )

        return {
            "overall_compliance_score": overall_score,
            "total_slots": total_slots_count,
            "compliant_slots": compliant_slots_count,
            "misplaced_slots": misplaced_slots_count,
            "empty_slots": empty_slots_count,
            "unexpected_slots": unexpected_slots_count,
            "violations": violations,
            "zone_audits": zone_audits
        }
