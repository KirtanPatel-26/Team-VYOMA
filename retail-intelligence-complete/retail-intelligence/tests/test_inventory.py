from app.inventory.counter import InventoryCounter


def test_inventory_count():
    class D:
        def __init__(self, name):
            self.product_name = name

    result = InventoryCounter().count([D("Fanta Orange"), D("Fanta Orange"), D("Oreo")])
    assert result["Fanta Orange"] == 2
    assert result["Oreo"] == 1
