from typing import Dict, Any, Optional

class StockAnalyzer:
    """
    Analyzes retail shelf inventory by correlating:
    1. Edge Vision shelf facing count (what camera sees right now on the shelf)
    2. Billing & Restock Ledger True Stock (accurate physical inventory derived from sales)
    
    Identifies:
    - Shelf Out of Stock (OOS) / Low Stock
    - Discrepancy signals:
        * RESTOCK_NEEDED_SHELF: units exist in store ledger, but shelf face is depleted (bring from backroom).
        * SHRINKAGE_AUDIT: camera detects more items than ledger accounts for (potential misplaced item or unrecorded delivery).
        * BALANCED: vision and ledger align.
    """
    def __init__(self, catalog):
        self.catalog = catalog

    def analyze(self, counts: Dict[str, int], ledger_stocks: Optional[Dict[str, int]] = None) -> Dict[str, Any]:
        output = []
        total_detected_items = 0
        total_ledger_items = 0
        total_value = 0.0
        discrepancy_count = 0

        for product in self.catalog.all():
            prod_id = product["id"]
            name = product["name"]
            shelf_facing = int(counts.get(name, 0))
            minimum = int(product.get("minimum_stock", 2))
            price = float(product.get("price", 0.0))
            cost_price = float(product.get("cost_price", price * 0.65))
            shelf_zone = product.get("target_shelf_zone", "Shelf")

            # Determine true stock from ledger if provided
            if ledger_stocks is not None and prod_id in ledger_stocks:
                true_stock = int(ledger_stocks[prod_id])
            elif ledger_stocks is not None and name in ledger_stocks:
                true_stock = int(ledger_stocks[name])
            else:
                true_stock = shelf_facing

            # Status based on shelf facing visibility
            if shelf_facing == 0:
                status = "OUT_OF_STOCK"
                health = 0
            elif shelf_facing <= minimum:
                status = "LOW_STOCK"
                health = int((shelf_facing / (minimum * 2)) * 100)
            else:
                status = "IN_STOCK"
                health = 100

            # Discrepancy comparison between Vision and Billing Ledger
            if ledger_stocks is not None:
                if true_stock > shelf_facing:
                    discrepancy = "RESTOCK_NEEDED_SHELF"
                    discrepancy_desc = f"{true_stock - shelf_facing} units in inventory, but shelf face has only {shelf_facing}"
                    discrepancy_count += 1
                elif shelf_facing > true_stock:
                    discrepancy = "SHRINKAGE_AUDIT"
                    discrepancy_desc = f"Shelf shows {shelf_facing}, but ledger records {true_stock}"
                    discrepancy_count += 1
                else:
                    discrepancy = "BALANCED"
                    discrepancy_desc = "Shelf facing and ledger match perfectly"
            else:
                discrepancy = "UNTRACKED"
                discrepancy_desc = "Ledger synchronization pending"

            total_detected_items += shelf_facing
            total_ledger_items += true_stock
            total_value += shelf_facing * price

            output.append({
                "product_id": prod_id,
                "product_name": name,
                "category": product.get("category", "General"),
                "price": price,
                "cost_price": cost_price,
                "margin": round(price - cost_price, 2),
                "stock": shelf_facing, # Kept for backward compatibility
                "shelf_facing_count": shelf_facing,
                "ledger_stock": true_stock,
                "minimum_stock": minimum,
                "status": status,
                "health_percentage": health,
                "shelf_zone": shelf_zone,
                "discrepancy": discrepancy,
                "discrepancy_desc": discrepancy_desc,
                "total_value": round(shelf_facing * price, 2)
            })

        return {
            "items": output,
            "total_detected_units": total_detected_items,
            "total_ledger_units": total_ledger_items,
            "total_discrepancies": discrepancy_count,
            "total_inventory_value": round(total_value, 2),
            "stock_health_score": round(sum(i["health_percentage"] for i in output) / max(1, len(output)), 1)
        }
