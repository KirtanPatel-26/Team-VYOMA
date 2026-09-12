"""
SmartRetail AI - Retail Store Brain
===================================
Autonomous decision and reasoning engine that converts raw edge computer vision
detections into predictive operational intelligence, explainable reasoning ("Why?"),
and prioritized prescriptive actions.
"""

import time
from datetime import datetime, timedelta
from collections import defaultdict
from typing import List, Dict, Any

class RetailStoreBrain:
    def __init__(self, catalog=None):
        self.catalog = catalog
        self.stock_history = defaultdict(list) # sku -> list of (timestamp, stock_count)
        self.traffic_history = [] # list of (timestamp, customer_count)
        self.start_time = time.time()

    def update(
        self,
        stock_items: List[Dict[str, Any]],
        traffic_data: Dict[str, Any],
        queue_data: Dict[str, Any],
        shelf_audit: Dict[str, Any]
    ) -> Dict[str, Any]:
        now = time.time()
        curr_customers = traffic_data.get("current_customers", 0)
        self.traffic_history.append((now, curr_customers))
        if len(self.traffic_history) > 30:
            self.traffic_history.pop(0)

        # Baseline traffic comparison
        traffic_trend_pct = 0
        if len(self.traffic_history) >= 5:
            avg_past = sum(c for _, c in self.traffic_history[:5]) / 5.0
            avg_recent = sum(c for _, c in self.traffic_history[-5:]) / 5.0
            if avg_past > 0:
                traffic_trend_pct = round(((avg_recent - avg_past) / avg_past) * 100.0, 1)

        sku_insights = []
        prioritized_actions = []

        for item in stock_items:
            sku = item.get("product_id")
            name = item.get("product_name")
            stock = item.get("stock", 0)
            min_stock = item.get("minimum_stock", 2)
            shelf_zone = item.get("shelf_zone", "Shelf Area")
            price = item.get("price", 35.0)

            # Record stock history
            self.stock_history[sku].append((now, stock))
            if len(self.stock_history[sku]) > 25:
                self.stock_history[sku].pop(0)

            # 1. Compute Velocity (units per hour)
            # Default realistic retail velocity based on current footfall
            base_hourly_velocity = max(0.6, (min_stock * 0.8)) # baseline
            if len(self.stock_history[sku]) >= 3:
                t0, c0 = self.stock_history[sku][0]
                t1, c1 = self.stock_history[sku][-1]
                dt_hours = (t1 - t0) / 3600.0
                if dt_hours > 0.005 and c0 > c1:
                    measured = (c0 - c1) / dt_hours
                    base_hourly_velocity = max(0.5, measured)

            # Traffic surge multiplier
            surge_multiplier = max(0.8, min(2.5, 1.0 + (traffic_trend_pct / 100.0)))
            velocity_per_hour = round(base_hourly_velocity * surge_multiplier, 1)
            velocity_per_min = round(velocity_per_hour / 60.0, 3)

            # 2. Predicted Stockout ETA
            if stock == 0:
                eta_minutes = 0
                eta_formatted = "DEPLETED (0m)"
                risk = "CRITICAL"
                confidence = 98
            else:
                eta_minutes = round(stock / max(0.001, velocity_per_min), 1)
                hours = int(eta_minutes // 60)
                mins = int(eta_minutes % 60)
                if hours > 0:
                    eta_formatted = f"{hours}h {mins}m"
                else:
                    eta_formatted = f"{mins}m"

                if eta_minutes <= 120 or stock <= min_stock:
                    risk = "CRITICAL" if stock <= 1 else "HIGH"
                    confidence = 92
                elif eta_minutes <= 300:
                    risk = "MODERATE"
                    confidence = 86
                else:
                    risk = "OPTIMAL"
                    confidence = 94

            # 3. Explainable AI ("Why is this SKU at risk?")
            if stock == 0:
                why_explanation = (
                    f"• Stock reached zero on {shelf_zone}.\n"
                    f"• Consumption velocity was {velocity_per_hour} units/hour.\n"
                    f"• No restock detected in recent frames.\n"
                    f"• Immediate customer walkout risk."
                )
                recommended_action = f"Refill {name} on {shelf_zone} IMMEDIATELY (Required: {min_stock * 2} units)"
                deadline_mins = 10
            elif risk in ["CRITICAL", "HIGH"]:
                drop_pct = 0
                if len(self.stock_history[sku]) >= 2:
                    init_c = max(stock, self.stock_history[sku][0][1])
                    if init_c > 0:
                        drop_pct = round(((init_c - stock) / init_c) * 100.0)

                why_explanation = (
                    f"• Shelf capacity at {round((stock / max(1, min_stock * 2)) * 100)}% ({stock} units left).\n"
                    f"• Sales velocity elevated at {velocity_per_hour} units/hour.\n"
                    f"• Store traffic {f'+{traffic_trend_pct}%' if traffic_trend_pct >= 0 else f'{traffic_trend_pct}%'} vs baseline.\n"
                    f"• Predicted stockout in {eta_formatted} without replenishment."
                )
                recommended_action = f"Refill {name} within {max(15, int(eta_minutes * 0.4))} minutes (+{min_stock * 2} units)"
                deadline_mins = max(15, int(eta_minutes * 0.4))
            else:
                why_explanation = (
                    f"• Healthy inventory buffer ({stock} units in stock, threshold is {min_stock}).\n"
                    f"• Consumption rate stable at {velocity_per_hour} units/hour.\n"
                    f"• Estimated runtime remaining: {eta_formatted}."
                )
                recommended_action = "No immediate action required. Monitoring consumption."
                deadline_mins = int(eta_minutes)

            # Revenue at risk
            revenue_at_risk = round(price * max(1, min_stock * 2), 2)

            insight = {
                "sku_id": sku,
                "product_name": name,
                "shelf_zone": shelf_zone,
                "current_stock": stock,
                "min_stock": min_stock,
                "sales_velocity_hourly": velocity_per_hour,
                "sales_velocity_minutely": velocity_per_min,
                "stockout_eta_minutes": eta_minutes,
                "stockout_eta_formatted": eta_formatted,
                "risk_level": risk,
                "confidence_score": confidence,
                "why_reasoning": why_explanation,
                "recommended_action": recommended_action,
                "action_deadline_minutes": deadline_mins,
                "revenue_at_risk": revenue_at_risk,
                "unit_price": price
            }
            sku_insights.append(insight)

            if risk in ["CRITICAL", "HIGH"]:
                prioritized_actions.append({
                    "priority": 1 if risk == "CRITICAL" else 2,
                    "type": "RESTOCK",
                    "target": name,
                    "zone": shelf_zone,
                    "action": recommended_action,
                    "eta_risk": eta_formatted,
                    "deadline_mins": deadline_mins,
                    "revenue_at_risk": revenue_at_risk
                })

        # 4. Check Queue & Planogram Prescriptive Actions
        if queue_data.get("congestion"):
            prioritized_actions.append({
                "priority": 1,
                "type": "QUEUE_DISPATCH",
                "target": "Checkout Counter",
                "zone": "Billing Area",
                "action": f"Open Billing Counter 2 ({queue_data.get('queue_length', 0)} shoppers waiting, ~{queue_data.get('estimated_wait_time_min', 0)}m wait)",
                "eta_risk": "Imminent checkout abandonment",
                "deadline_mins": 5,
                "revenue_at_risk": round(queue_data.get("queue_length", 3) * 180.0, 2)
            })

        for shelf in shelf_audit.get("shelves", []):
            if shelf.get("status") == "MISPLACED_ITEMS":
                misplaced = shelf.get("misplaced_items", [])
                prioritized_actions.append({
                    "priority": 3,
                    "type": "PLANOGRAM_CORRECTION",
                    "target": f"{', '.join(misplaced)}",
                    "zone": shelf.get("zone", "Shelf"),
                    "action": f"MOVE PRODUCT: Return {', '.join(misplaced)} to correct category bay",
                    "eta_risk": "Customer search friction",
                    "deadline_mins": 45,
                    "revenue_at_risk": 0.0
                })

        # Sort actions by priority (1 = highest) and revenue at risk
        prioritized_actions.sort(key=lambda x: (x["priority"], -x["revenue_at_risk"]))

        return {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "sku_predictions": sku_insights,
            "top_prioritized_actions": prioritized_actions[:5],
            "traffic_surge_pct": traffic_trend_pct,
            "critical_risk_count": sum(1 for s in sku_insights if s["risk_level"] == "CRITICAL"),
            "high_risk_count": sum(1 for s in sku_insights if s["risk_level"] == "HIGH")
        }
