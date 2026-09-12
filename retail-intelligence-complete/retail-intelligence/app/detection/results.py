from dataclasses import dataclass
from typing import Optional, Tuple

@dataclass
class Detection:
    class_id: int
    class_name: str
    confidence: float
    bbox: Tuple[int, int, int, int]
    track_id: Optional[int] = None
    product_name: Optional[str] = None
    sku_id: Optional[str] = None
    person_type: Optional[str] = "customer" # "customer" or "staff"
    staff_role: Optional[str] = None # e.g. "Floor Associate", "Cashier"
    source: str = "trained_sku_model" # "trained_sku_model", "person_model", or "demo_simulation"

    def to_dict(self):
        return {
            "class_id": self.class_id,
            "class_name": self.class_name,
            "confidence": round(self.confidence, 3),
            "bbox": list(self.bbox),
            "track_id": self.track_id,
            "product_name": self.product_name,
            "sku_id": self.sku_id,
            "person_type": self.person_type,
            "staff_role": self.staff_role,
            "source": self.source
        }
