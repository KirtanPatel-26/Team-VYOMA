import json
from pathlib import Path

class ProductCatalog:
    def __init__(self, path):
        self.path = Path(path)
        self.products = json.loads(self.path.read_text(encoding="utf-8"))

    def all(self):
        return self.products

    def by_id(self, product_id):
        return next((p for p in self.products if p["id"] == product_id), None)

    def get(self, product_id):
        return self.by_id(product_id)

    def by_name(self, name):
        name = name.lower()
        return next((p for p in self.products if p["name"].lower() == name), None)

    def find_by_name(self, name):
        return self.by_name(name)
