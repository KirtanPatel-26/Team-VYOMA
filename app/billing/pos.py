import time
from typing import Dict, List, Any, Optional
from datetime import datetime

from app.products.catalog import ProductCatalog
from app.billing.ledger import InventoryLedger

class BillingService:
    """
    POS Billing Service for retail store checkouts:
    - Validates SKUs and active prices against ProductCatalog
    - Computes line totals, GST/taxes, and total bill
    - Interacts atomically with InventoryLedger to decrement true stock
    - Generates standardized digital receipts
    """

    def __init__(self, catalog: ProductCatalog, ledger: InventoryLedger):
        self.catalog = catalog
        self.ledger = ledger

    def process_sale(
        self,
        items: List[Dict[str, Any]],
        payment_method: str = "UPI",
        cashier: str = "Self_Checkout_01"
    ) -> Dict[str, Any]:
        """
        Processes a customer checkout:
        - items: [{"sku_id": "SKU001", "quantity": 2}, ...]
        """
        if not items:
            raise ValueError("Sale must contain at least one item")

        validated_items = []
        total_amount = 0.0

        for item in items:
            sku_id = item.get("sku_id")
            qty = int(item.get("quantity", 1))

            if qty <= 0:
                raise ValueError(f"Quantity for {sku_id} must be greater than 0")

            product = self.catalog.get(sku_id)
            if not product:
                # Also try finding by name if sku_id was passed as product name
                product = self.catalog.find_by_name(sku_id)
                if product:
                    sku_id = product["id"]
                else:
                    raise ValueError(f"SKU '{sku_id}' not found in product catalog")

            unit_price = float(product.get("price", 0.0))
            line_total = round(qty * unit_price, 2)
            total_amount += line_total

            validated_items.append({
                "sku_id": sku_id,
                "product_name": product.get("name", sku_id),
                "category": product.get("category", "General"),
                "quantity": qty,
                "unit_price": unit_price,
                "line_total": line_total
            })

        total_amount = round(total_amount, 2)
        transaction_id = f"TXN_{int(time.time() * 1000)}"
        now_iso = datetime.now().isoformat()

        # Record into ledger and sales table
        ledger_res = self.ledger.record_sale(
            transaction_id=transaction_id,
            items=validated_items,
            total_amount=total_amount,
            payment_method=payment_method,
            cashier=cashier
        )

        receipt = {
            "success": True,
            "transaction_id": transaction_id,
            "timestamp": now_iso,
            "cashier": cashier,
            "payment_method": payment_method,
            "items": validated_items,
            "subtotal": total_amount,
            "tax": round(total_amount * 0.05, 2), # 5% GST display item
            "total_amount": total_amount,
            "updated_stocks": ledger_res["updated_stocks"],
            "currency": "INR",
            "store_id": "STORE_001"
        }
        return receipt
