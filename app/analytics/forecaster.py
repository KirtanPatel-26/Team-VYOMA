import time
from collections import defaultdict

class StockoutForecaster:
    """
    Predictive Stockout & Demand Velocity Forecaster.
    Uses real-time consumption velocity and customer footfall density to project
    exact minutes remaining before shelf depletion and suggest batch restock sizes.
    """
    def __init__(self, catalog):
        self.catalog = catalog
        self.history = defaultdict(list) # sku -> list of (timestamp, count)

    def update_and_forecast(self, stock_items, current_footfall=5):
        now = time.time()
        forecasts = []

        for item in stock_items:
            sku = item["product_id"]
            name = item["product_name"]
            current_stock = item["stock"]
            min_stock = item["minimum_stock"]

            self.history[sku].append((now, current_stock))
            # Keep last 20 readings
            if len(self.history[sku]) > 20:
                self.history[sku].pop(0)

            # Calculate consumption velocity (units per minute)
            velocity = 0.25 # baseline demand rate (1 unit every 4 mins during active store hours)
            if len(self.history[sku]) >= 2:
                t_first, c_first = self.history[sku][0]
                t_last, c_last = self.history[sku][-1]
                dt_min = (t_last - t_first) / 60.0
                if dt_min > 0.1 and c_first > c_last:
                    velocity = max(0.1, (c_first - c_last) / dt_min)

            # Adjust velocity by current store footfall
            footfall_factor = max(0.8, min(2.5, current_footfall / 4.0))
            adjusted_velocity = velocity * footfall_factor

            if current_stock == 0:
                mins_remaining = 0
                urgency = "CRITICAL (DEPLETED)"
                recommended_restock = max(6, min_stock * 3)
            else:
                mins_remaining = round(current_stock / adjusted_velocity, 1)
                if mins_remaining < 15:
                    urgency = "HIGH (RESTOCK SOON)"
                    recommended_restock = max(4, min_stock * 2)
                elif mins_remaining < 45:
                    urgency = "MODERATE"
                    recommended_restock = min_stock
                else:
                    urgency = "OPTIMAL"
                    recommended_restock = 0

            forecasts.append({
                "product_id": sku,
                "product_name": name,
                "current_stock": current_stock,
                "depletion_velocity": round(adjusted_velocity, 2), # units/min
                "estimated_minutes_remaining": mins_remaining,
                "urgency": urgency,
                "recommended_restock_units": recommended_restock,
                "projected_revenue_loss": round((recommended_restock or 4) * item.get("price", 35.0), 2)
            })

        return forecasts
