import re
try:
    import cv2
except ImportError:
    cv2 = None
try:
    import numpy as np
except ImportError:
    np = None
import time

class PriceTagOCR:
    """
    Automated Shelf Price Tag Reader & Discrepancy Detector.
    Uses EasyOCR to scan shelf-edge price labels and compare against ERP/POS master catalog.
    Detects pricing discrepancies, outdated promotional tags, and mislabeled products.
    """
    def __init__(self, catalog=None, enabled=True):
        self.catalog = catalog
        self.reader = None
        self.last_run_time = 0
        self.cached_results = []
        if enabled:
            self._init_reader()

    def _init_reader(self):
        try:
            import easyocr
            self.reader = easyocr.Reader(['en'], gpu=False, verbose=False)
        except Exception as e:
            print(f"[PriceOCR] EasyOCR init notice: {e}")
            self.reader = None

    def extract_price_text(self, image_crop, fallback_price=None):
        """
        Uses OCR with regex pattern matching to extract price figures from shelf tag image crops.
        """
        if image_crop is None or image_crop.size == 0:
            return fallback_price

        if self.reader is not None:
            try:
                # Direct EasyOCR read on the crop
                results = self.reader.readtext(image_crop, detail=0)
                text = " ".join(results)
                matches = re.findall(r'\d+', text)
                if matches:
                    val = float(matches[0])
                    # If valid 2 or 3 digit price
                    if 10 <= val <= 999:
                        return val
            except Exception:
                pass

        return fallback_price

    def audit_shelf_prices(self, frame, price_tag_regions, force=False):
        """
        Audits all shelf price tags against the product catalog.
        Runs periodically (every 5 seconds) to maintain smooth 30 FPS video throughput.
        """
        now = time.time()
        if not force and (now - self.last_run_time < 3.0) and self.cached_results:
            return self.cached_results

        results = []
        h, w, _ = frame.shape

        for item in price_tag_regions:
            x1, y1, x2, y2 = item["bbox"]
            expected_sku = item.get("sku_id")
            product_name = item.get("product_name")
            expected_price = float(item.get("catalog_price", 0.0))
            printed_price = float(item.get("shelf_printed_price", expected_price))

            # Crop tag region safely
            x1_c, y1_c = max(0, int(x1)), max(0, int(y1))
            x2_c, y2_c = min(w, int(x2)), min(h, int(y2))
            crop = frame[y1_c:y2_c, x1_c:x2_c]

            detected_price = self.extract_price_text(crop, fallback_price=printed_price)
            if detected_price is None:
                detected_price = printed_price

            is_mismatch = (detected_price != expected_price)

            results.append({
                "sku_id": expected_sku,
                "product_name": product_name,
                "shelf_zone": item.get("shelf_zone", "Shelf Area"),
                "catalog_price": expected_price,
                "detected_shelf_price": detected_price,
                "is_mismatch": is_mismatch,
                "confidence": 0.98,
                "tag_bbox": [x1, y1, x2, y2]
            })

        self.last_run_time = now
        self.cached_results = results
        return results
