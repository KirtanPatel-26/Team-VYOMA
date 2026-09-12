import time
from datetime import datetime

def build_alerts(stock_items, queue_data, shelf_audit=None, price_audit=None, brain_data=None):
    alerts = []
    now = datetime.now()
    current_time_str = now.strftime("%H:%M:%S")
    iso_timestamp = now.isoformat()

    brain_map = {}
    if brain_data and isinstance(brain_data, dict):
        for p in brain_data.get("sku_predictions", []):
            brain_map[p.get("sku_id")] = p

    # 1. Stock Out & Low Stock Alerts
    for item in stock_items:
        sku = item.get("product_id")
        b_info = brain_map.get(sku, {})
        eta = b_info.get("stockout_eta_formatted", "")
        vel = b_info.get("sales_velocity_hourly")
        rev_risk = b_info.get("revenue_at_risk", round(item.get("price", 35.0) * max(1, item.get("minimum_stock", 2) * 2), 2))

        if item["status"] == "OUT_OF_STOCK":
            alerts.append({
                "id": f"oos_{sku}",
                "type": "OUT_OF_STOCK",
                "severity": "critical",
                "title": f"Out of Stock: {item['product_name']}",
                "message": f"Stock depleted to 0 (minimum required: {item['minimum_stock']}). High walkout risk. Revenue at risk: ₹{rev_risk:.2f}.",
                "zone": item.get("shelf_zone", "Shelf Area"),
                "action": f"Restock {item['product_name']} immediately",
                "stockout_eta": "0m (DEPLETED)",
                "revenue_at_risk": rev_risk,
                "timestamp": current_time_str,
                "iso_timestamp": iso_timestamp
            })
        elif item["status"] == "LOW_STOCK":
            vel_str = f" Velocity: {vel} units/hr." if vel is not None else ""
            eta_str = f" Stockout predicted in {eta}." if eta else ""
            alerts.append({
                "id": f"low_{sku}",
                "type": "LOW_STOCK",
                "severity": "warning",
                "title": f"Low Stock: {item['product_name']}",
                "message": f"Only {item['stock']} unit(s) remaining (threshold: {item['minimum_stock']}).{vel_str}{eta_str}",
                "zone": item.get("shelf_zone", "Shelf Area"),
                "action": f"Schedule replenishment for {item['product_name']}",
                "stockout_eta": eta or "Under 2 hours",
                "revenue_at_risk": rev_risk,
                "timestamp": current_time_str,
                "iso_timestamp": iso_timestamp
            })

    # 2. Queue Congestion Alerts
    if queue_data and queue_data.get("congestion"):
        q_len = queue_data.get("queue_length", 0)
        alerts.append({
            "id": "queue_congestion",
            "type": "QUEUE_CONGESTION",
            "severity": "critical",
            "title": f"High Queue Congestion: {q_len} Customers in Line",
            "message": f"Estimated customer wait time is {queue_data.get('estimated_wait_time_min', 0)} mins. {queue_data.get('recommendation', '')}",
            "zone": "Checkout Counter",
            "action": "Deploy Staff & Open Additional Billing Counter",
            "stockout_eta": "Immediate Walkout Risk",
            "revenue_at_risk": round(q_len * 180.0, 2),
            "timestamp": current_time_str,
            "iso_timestamp": iso_timestamp
        })

    # 3. EasyOCR Shelf Price Tag Mismatch Alerts
    if price_audit:
        for p in price_audit:
            if p.get("is_mismatch"):
                alerts.append({
                    "id": f"price_mismatch_{p.get('sku_id')}",
                    "type": "PRICE_TAG_MISMATCH",
                    "severity": "warning",
                    "title": f"EasyOCR Price Mismatch: {p.get('product_name')}",
                    "message": f"Shelf-edge price tag reads Rs {p.get('detected_shelf_price'):.2f}, but POS catalog price is Rs {p.get('catalog_price'):.2f}.",
                    "zone": p.get("shelf_zone", "Shelf Bay"),
                    "action": "Correct shelf price label to avoid customer dispute",
                    "stockout_eta": "Compliance Issue",
                    "revenue_at_risk": 0.0,
                    "timestamp": current_time_str,
                    "iso_timestamp": iso_timestamp
                })

    # 4. Planogram Compliance Alerts
    if shelf_audit and "shelves" in shelf_audit:
        for shelf in shelf_audit["shelves"]:
            if shelf["status"] == "EMPTY_SLOT":
                alerts.append({
                    "id": f"empty_slot_{shelf['shelf_code']}",
                    "type": "PLANOGRAM_MISMATCH",
                    "severity": "warning",
                    "title": f"Empty Shelf Bay in {shelf['zone']}",
                    "message": f"All items in {shelf['zone']} are depleted. Shelf void detected.",
                    "zone": shelf["zone"],
                    "action": "Restock shelf bay according to planogram",
                    "stockout_eta": "Void Detected",
                    "revenue_at_risk": 500.0,
                    "timestamp": current_time_str,
                    "iso_timestamp": iso_timestamp
                })
            elif shelf["status"] == "MISPLACED_ITEMS":
                misplaced = shelf.get("misplaced_items", [])
                alerts.append({
                    "id": f"misplaced_{shelf['shelf_code']}",
                    "type": "PLANOGRAM_MISMATCH",
                    "severity": "info",
                    "title": f"Planogram Discrepancy in {shelf['zone']}",
                    "message": f"Misplaced items detected: {', '.join(misplaced)}. Move directives issued.",
                    "zone": shelf["zone"],
                    "action": f"MOVE PRODUCT: Relocate {', '.join(misplaced)} to correct category bay",
                    "stockout_eta": "Planogram Audit",
                    "revenue_at_risk": 0.0,
                    "timestamp": current_time_str,
                    "iso_timestamp": iso_timestamp
                })

    # Prioritize: critical first, then warning, then info; then by revenue_at_risk desc
    sev_rank = {"critical": 0, "warning": 1, "info": 2}
    alerts.sort(key=lambda a: (sev_rank.get(a.get("severity", "info"), 3), -a.get("revenue_at_risk", 0)))

    return alerts
