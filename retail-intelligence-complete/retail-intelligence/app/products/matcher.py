class ProductMatcher:
    """
    Maps detector class names to SKU names.
    Replace/extend this with an embedding or custom YOLO SKU matcher later.
    """

    def __init__(self, mapping=None):
        self.mapping = {k.lower(): v for k, v in (mapping or {}).items()}

    def match(self, class_name):
        return self.mapping.get(class_name.lower())
