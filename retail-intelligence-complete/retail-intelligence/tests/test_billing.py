import pytest
import tempfile
from pathlib import Path
from app.database.local import LocalDatabase
from app.billing.ledger import InventoryLedger
from app.billing.pos import BillingService
from app.products.catalog import ProductCatalog

@pytest.fixture
def setup_billing():
    temp_dir = tempfile.TemporaryDirectory()
    db_path = Path(temp_dir.name) / "test_retail.db"
    db = LocalDatabase(db_path)
    ledger = InventoryLedger(db)
    
    catalog_path = Path(__file__).resolve().parents[1] / "data" / "products.json"
    catalog = ProductCatalog(catalog_path)
    pos = BillingService(catalog, ledger)
    
    yield db, ledger, pos, catalog
    temp_dir.cleanup()

def test_ledger_append_only_stock(setup_billing):
    db, ledger, pos, catalog = setup_billing
    
    # 1. Initial stock is 0
    assert ledger.get_true_stock("SKU001") == 0
    
    # 2. Restock 20 units
    restock_res = ledger.record_restock("SKU001", 20, note="Batch #101 arrival", actor="Manager")
    assert restock_res["new_true_stock"] == 20
    assert ledger.get_true_stock("SKU001") == 20
    
    # 3. Restock another 5 units
    ledger.record_restock("SKU001", 5, note="Batch #102")
    assert ledger.get_true_stock("SKU001") == 25
    
    # 4. Sell 3 units via POS checkout
    sale_res = pos.process_sale([{"sku_id": "SKU001", "quantity": 3}], payment_method="UPI", cashier="Cashier_A")
    assert sale_res["success"] is True
    assert sale_res["total_amount"] == 35.0 * 3
    assert ledger.get_true_stock("SKU001") == 22
    
    # 5. Verify ledger history has 3 movements: 2 restocks + 1 sale
    history = ledger.get_history("SKU001")
    assert len(history) == 3
    assert history[0]["reason"] == "sale"
    assert history[0]["change_qty"] == -3
    assert history[1]["reason"] == "restock"
    assert history[1]["change_qty"] == 5
    assert history[2]["reason"] == "restock"
    assert history[2]["change_qty"] == 20

def test_pos_multi_item_checkout_and_receipt(setup_billing):
    db, ledger, pos, catalog = setup_billing
    
    # Seed stock
    ledger.record_restock("SKU001", 10) # Fanta (35)
    ledger.record_restock("SKU003", 10) # Oreo (30)
    
    items = [
        {"sku_id": "SKU001", "quantity": 2}, # 70
        {"sku_id": "SKU003", "quantity": 1}  # 30
    ]
    receipt = pos.process_sale(items, payment_method="Cash", cashier="Cashier_B")
    
    assert receipt["success"] is True
    assert receipt["subtotal"] == 100.0
    assert receipt["total_amount"] == 100.0
    assert receipt["payment_method"] == "Cash"
    assert len(receipt["items"]) == 2
    assert receipt["updated_stocks"]["SKU001"] == 8
    assert receipt["updated_stocks"]["SKU003"] == 9
