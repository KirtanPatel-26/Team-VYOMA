import json
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
from shapely.geometry import Point, Polygon

from app.config.settings import DATA_DIR

ZONES_FILE = DATA_DIR / "theft_zones.json"

class StoreZone:
    """Represents a store zone (polygon or bounding box) with a specific type and ID."""
    def __init__(
        self,
        zone_id: str,
        name: str,
        zone_type: str, # "SHELF_ZONE", "CHECKOUT_ZONE", "EXIT_ZONE", "AISLE_ZONE", "RESTRICTED_ZONE"
        coordinates: List[Any], # Either [x1, y1, x2, y2] or [[x1, y1], [x2, y2], ...]
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.zone_id = zone_id
        self.name = name
        self.zone_type = zone_type.upper()
        self.coordinates = coordinates
        self.metadata = metadata or {}
        
        # Build Shapely polygon for robust geometric point-in-polygon checks
        self.polygon = self._build_polygon(coordinates)
        self.bbox = self._calculate_bbox()

    def _build_polygon(self, coords: List[Any]) -> Polygon:
        # Check if rectangle [x1, y1, x2, y2]
        if len(coords) == 4 and all(isinstance(c, (int, float)) for c in coords):
            x1, y1, x2, y2 = coords
            return Polygon([(x1, y1), (x2, y1), (x2, y2), (x1, y2)])
        elif len(coords) >= 3:
            # List of points [[x, y], ...]
            pts = [(p[0], p[1]) for p in coords]
            return Polygon(pts)
        else:
            # Fallback zero polygon
            return Polygon([(0, 0), (0, 0), (0, 0)])

    def _calculate_bbox(self) -> Tuple[int, int, int, int]:
        minx, miny, maxx, maxy = self.polygon.bounds
        return (int(minx), int(miny), int(maxx), int(maxy))

    def contains_point(self, cx: float, cy: float) -> bool:
        return self.polygon.contains(Point(cx, cy)) or self.polygon.touches(Point(cx, cy))

    def distance_to_point(self, cx: float, cy: float) -> float:
        return self.polygon.distance(Point(cx, cy))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "name": self.name,
            "zone_type": self.zone_type,
            "coordinates": self.coordinates,
            "bbox": list(self.bbox),
            "metadata": self.metadata
        }

class StoreZoneManager:
    """
    Manages configurable store zones across multiple CCTV cameras.
    Reads and synchronizes with existing shelves.json layout.
    """
    def __init__(self, camera_id: str = "camera_01"):
        self.camera_id = camera_id
        self.zones: List[StoreZone] = []
        self._load_zones()

    def _load_zones(self):
        # 1. First check if theft_zones.json exists
        if ZONES_FILE.exists():
            try:
                with open(ZONES_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    cam_data = data.get(self.camera_id) or data.get("default", [])
                    self.zones = [
                        StoreZone(
                            zone_id=z["zone_id"],
                            name=z["name"],
                            zone_type=z["zone_type"],
                            coordinates=z["coordinates"],
                            metadata=z.get("metadata", {})
                        )
                        for z in cam_data
                    ]
                    if self.zones:
                        return
            except Exception as e:
                print(f"[StoreZoneManager] Warning loading theft_zones.json: {e}")

        # 2. Fallback to initializing from existing shelves.json
        self._init_from_shelves_config()

    def _init_from_shelves_config(self):
        shelves_config_path = DATA_DIR / "shelves.json"
        shelves_data = {}
        if shelves_config_path.exists():
            try:
                with open(shelves_config_path, "r", encoding="utf-8") as f:
                    shelves_data = json.load(f)
            except Exception:
                pass

        zones_list = []
        # Shelf zones
        for z in shelves_data.get("zones", []):
            code = z.get("shelf_code") or z.get("name", "SHELF")
            zones_list.append(StoreZone(
                zone_id=code,
                name=z.get("name", code),
                zone_type="SHELF_ZONE",
                coordinates=z["bbox"],
                metadata={
                    "category": z.get("category", ""),
                    "expected_skus": z.get("expected_skus", []),
                    "expected_names": z.get("expected_names", [])
                }
            ))

        # Checkout / Queue Zone
        q_bbox = shelves_data.get("queue_zone", [830, 360, 1240, 680])
        zones_list.append(StoreZone(
            zone_id="CHECKOUT_01",
            name="Checkout & POS Counters",
            zone_type="CHECKOUT_ZONE",
            coordinates=q_bbox,
            metadata={"counters": 2}
        ))

        # Exit Zone (Corridor / Space between Shelf C and Billing Counter)
        exit_bbox = shelves_data.get("exit_zone", [760, 270, 1280, 359])
        zones_list.append(StoreZone(
            zone_id="EXIT_01",
            name="Exit Point (Between Shelf C & Billing Counter)",
            zone_type="EXIT_ZONE",
            coordinates=exit_bbox,
            metadata={"gate": "Corridor between Shelf C and Billing Counter"}
        ))

        # Entrance Zone (Optional Aisle / Common Area entry)
        entrance_bbox = shelves_data.get("entrance_zone", [0, 200, 120, 720])
        zones_list.append(StoreZone(
            zone_id="ENTRANCE_01",
            name="Store Entrance Gate",
            zone_type="AISLE_ZONE",
            coordinates=entrance_bbox,
            metadata={"gate": "Main Entrance"}
        ))

        self.zones = zones_list
        self.save_zones()

    def save_zones(self) -> bool:
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            existing = {}
            if ZONES_FILE.exists():
                try:
                    with open(ZONES_FILE, "r", encoding="utf-8") as f:
                        existing = json.load(f)
                except Exception:
                    existing = {}

            existing[self.camera_id] = [z.to_dict() for z in self.zones]
            existing["default"] = existing[self.camera_id]

            with open(ZONES_FILE, "w", encoding="utf-8") as f:
                json.dump(existing, f, indent=2)
            return True
        except Exception as e:
            print(f"[StoreZoneManager] Error saving zones: {e}")
            return False

    def get_zone_at(self, cx: float, cy: float) -> Optional[StoreZone]:
        # Check in order of priority: EXIT_ZONE > CHECKOUT_ZONE > SHELF_ZONE > AISLE_ZONE
        type_priority = {"EXIT_ZONE": 1, "CHECKOUT_ZONE": 2, "RESTRICTED_ZONE": 3, "SHELF_ZONE": 4, "AISLE_ZONE": 5}
        sorted_zones = sorted(self.zones, key=lambda z: type_priority.get(z.zone_type, 10))
        for z in sorted_zones:
            if z.contains_point(cx, cy):
                return z
        return None

    def get_zone_name_at(self, cx: float, cy: float) -> str:
        z = self.get_zone_at(cx, cy)
        return z.name if z else "Aisle / Common Area"

    def get_zone_type_at(self, cx: float, cy: float) -> str:
        z = self.get_zone_at(cx, cy)
        return z.zone_type if z else "AISLE_ZONE"

    def get_shelf_zones(self) -> List[StoreZone]:
        return [z for z in self.zones if z.zone_type == "SHELF_ZONE"]

    def get_checkout_zones(self) -> List[StoreZone]:
        return [z for z in self.zones if z.zone_type == "CHECKOUT_ZONE"]

    def get_exit_zones(self) -> List[StoreZone]:
        return [z for z in self.zones if z.zone_type == "EXIT_ZONE"]

    def update_zones(self, new_zones_data: List[Dict[str, Any]]):
        self.zones = [
            StoreZone(
                zone_id=z.get("zone_id", f"ZONE_{i}"),
                name=z.get("name", "Zone"),
                zone_type=z.get("zone_type", "SHELF_ZONE"),
                coordinates=z["coordinates"],
                metadata=z.get("metadata", {})
            )
            for i, z in enumerate(new_zones_data)
        ]
        self.save_zones()

    def to_dict_list(self) -> List[Dict[str, Any]]:
        return [z.to_dict() for z in self.zones]
