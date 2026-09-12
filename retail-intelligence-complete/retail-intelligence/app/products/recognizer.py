from app.products.matcher import ProductMatcher

class ProductRecognizer:
    def __init__(self, matcher: ProductMatcher):
        self.matcher = matcher

    def recognize(self, detections):
        for detection in detections:
            if not detection.product_name:
                matched = self.matcher.match(detection.class_name)
                if matched:
                    detection.product_name = matched
        return detections
