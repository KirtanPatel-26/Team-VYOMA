import time
from typing import Dict, List, Optional, Any
from app.database.local import LocalDatabase

class InventoryLedger:
    """
    Append-only single source of truth for retail inventory.
    Current true stock is deterministically computed as:
        true_stock(sku) = SUM(change_qty)
    
    Supported movement reasons:
    - 'sale': negative change (decrements stock upon billing checkout)
    - 'restock': positive change (increments stock upon delivery arrival)
    - 'adjustment': positive/negative (manual reconciliation, audit correction)
    """

    def __init__(self, db: LocalDatabase):
        self.db = db

    def record_sale(
        self,
        transaction_id: str,
        items: List[Dict[str, Any]],
        total_amount: float,
        payment_method: str = "UPI",
        cashier: str = "POS_Term_01"
    ) -> Dict[str, Any]:
        """
        Atomically records a completed POS sale transaction and decrements
        the ledger for each line item sold.
        """
        self.db.record_sale_transaction(
            transaction_id=transaction_id,
            total_amount=total_amount,
            payment_method=payment_method,
            cashier=cashier,
            items=items
        )
        
        # Return updated stocks for all affected items
        updated_stocks = {
            item["sku_id"]: self.get_true_stock(item["sku_id"])
            for item in items
        }
        return {
            "transaction_id": transaction_id,
            "status": "RECORDED",
            "items_count": len(items),
            "updated_stocks": updated_stocks
        }

    def record_restock(
        self,
        sku_id: str,
        quantity: int,
        note: str = "Shipment received",
        actor: str = "Inventory Manager",
        reference_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Action: Add stock when it arrives from supplier/warehouse.
        Increments the ledger (+quantity).
        """
        if quantity <= 0:
            raise ValueError("Restock quantity must be positive")

        ref_id = reference_id or f"RESTOCK_{int(time.time())}"
        row_id = self.db.record_ledger_entry(
            sku_id=sku_id,
            change_qty=abs(quantity),
            reason="restock",
            reference_id=ref_id,
            note=note,
            actor=actor
        )

        new_stock = self.get_true_stock(sku_id)
        return {
            "ledger_id": row_id,
            "sku_id": sku_id,
            "quantity_added": quantity,
            "new_true_stock": new_stock,
            "reference_id": ref_id,
            "actor": actor
        }

    def record_adjustment(
        self,
        sku_id: str,
        change_qty: int,
        reason: str = "adjustment",
        note: str = "Physical count reconciliation",
        actor: str = "Store Auditor"
    ) -> Dict[str, Any]:
        """
        Manual inventory adjustment for reconciliation, damaged goods, or audit.
        """
        if change_qty == 0:
            raise ValueError("Adjustment change_qty cannot be 0")

        ref_id = f"ADJ_{int(time.time())}"
        row_id = self.db.record_ledger_entry(
            sku_id=sku_id,
            change_qty=change_qty,
            reason=reason,
            reference_id=ref_id,
            note=note,
            actor=actor
        )

        new_stock = self.get_true_stock(sku_id)
        return {
            "ledger_id": row_id,
            "sku_id": sku_id,
            "change_qty": change_qty,
            "new_true_stock": new_stock,
            "reference_id": ref_id,
            "actor": actor
        }

    def get_true_stock(self, sku_id: Optional[str] = None):
        """
        Derives true inventory stock directly from the immutable ledger:
        current_stock = SUM(change_qty).
        """
        return self.db.get_true_stock(sku_id)

    def get_all_true_stock(self) -> Dict[str, int]:
        """Returns true stock mapping for all SKUs in the database."""
        stock = self.db.get_true_stock()
        return stock if isinstance(stock, dict) else {}

    def get_history(self, sku_id: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Returns the full ledger audit log."""
        return self.db.get_ledger_history(sku_id=sku_id, limit=limit)

    def get_sales(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Returns recent sales transactions with receipts."""
        return self.db.get_sales_history(limit=limit)
