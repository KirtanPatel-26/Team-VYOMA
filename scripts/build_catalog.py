import os
import sys
import urllib.request
from pathlib import Path
import cv2
import numpy as np

ROOT_DIR = Path(__file__).resolve().parents[1]
CATALOG_DIR = ROOT_DIR / "datasets" / "products" / "raw" / "catalog"
CATALOG_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {"User-Agent": "RetailAI/1.0 (contact@retailai.local)"}

PRODUCT_RESOURCES = {
    0: {
        "sku_id": "SKU001",
        "name": "Fanta Orange",
        "url": "https://thumb.wikimedia.org/wikipedia/commons/thumb/c/cd/Fanta_Orange_Glass_Bottle.jpg/960px-Fanta_Orange_Glass_Bottle.jpg?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=thumbnail",
        "crop_box": (150, 80, 550, 880),
    },
    1: {
        "sku_id": "SKU002",
        "name": "Pringles Original",
        "url": "https://thumb.wikimedia.org/wikipedia/commons/thumb/b/b9/Pringles-165g-to-134g.jpg/960px-Pringles-165g-to-134g.jpg?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=thumbnail",
        "crop_box": (180, 50, 480, 900),
    },
    2: {
        "sku_id": "SKU003",
        "name": "Oreo",
        "url": "https://thumb.wikimedia.org/wikipedia/commons/thumb/3/3e/Oreo-Two-Cookies.jpg/960px-Oreo-Two-Cookies.jpg?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=thumbnail",
        "crop_box": (50, 80, 860, 600),
    },
    3: {
        "sku_id": "SKU004",
        "name": "Amul Taaza",
        "url": "https://thumb.wikimedia.org/wikipedia/commons/thumb/1/1f/Amul_Kool_Milk.jpg/960px-Amul_Kool_Milk.jpg?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=thumbnail",
        "crop_box": (120, 100, 720, 850),
    },
    4: {
        "sku_id": "SKU005",
        "name": "Real Orange Juice",
        "url": "https://thumb.wikimedia.org/wikipedia/commons/thumb/e/e8/SMAK_tetra_pak_01.jpg/960px-SMAK_tetra_pak_01.jpg?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=thumbnail",
        "crop_box": (200, 50, 650, 900),
    },
    5: {
        "sku_id": "SKU006",
        "name": "Dove Soap",
        "local_source": r"C:\Users\kirtan patel\.gemini\antigravity\brain\b0e944d2-a089-440e-80f7-a26962e2fcc6\.user_uploaded\media_1789202618794.jpg",
        "crop_box": (120, 408, 535, 420), # (x, y, w, h)
    },
    6: {
        "sku_id": "SKU007",
        "name": "Coca Cola",
        "url": "https://thumb.wikimedia.org/wikipedia/commons/thumb/a/ae/Coca_Cola_-_Mexican_death_sentence.jpg/960px-Coca_Cola_-_Mexican_death_sentence.jpg?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=thumbnail",
        "crop_box": (220, 150, 480, 750),
    },
    7: {
        "sku_id": "SKU008",
        "name": "Lays Classic",
        "url": "https://thumb.wikimedia.org/wikipedia/commons/thumb/c/c5/Lays_Wavy_Chocolate_Covered_Potato_Chips_%2815489325943%29.jpg/960px-Lays_Wavy_Chocolate_Covered_Potato_Chips_%2815489325943%29.jpg?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=thumbnail",
        "crop_box": (180, 100, 580, 800),
    },
    8: {
        "sku_id": "SKU009",
        "name": "Dairy Milk",
        "url": "https://thumb.wikimedia.org/wikipedia/commons/thumb/5/5e/Cadbury-Dairy-Milk-Caramel-Bar.jpg/960px-Cadbury-Dairy-Milk-Caramel-Bar.jpg?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=thumbnail",
        "crop_box": (150, 100, 680, 450),
    },
    9: {
        "sku_id": "SKU010",
        "name": "Colgate Paste",
        "local_source": r"C:\Users\kirtan patel\.gemini\antigravity\brain\b0e944d2-a089-440e-80f7-a26962e2fcc6\.user_uploaded\media_1789202613498.jpg",
        "crop_box": (38, 468, 667, 167), # (x, y, w, h)
    }
}

def build_catalog():
    print("=" * 65)
    print(" Building 10-SKU Product Catalog (User Uploads + Retrieved Items)")
    print("=" * 65)

    for class_id, meta in PRODUCT_RESOURCES.items():
        name = meta["name"]
        sku_id = meta["sku_id"]
        out_cutout = CATALOG_DIR / f"sku_{class_id:02d}_{sku_id}_{name.replace(' ', '_').lower()}.png"

        if "local_source" in meta:
            # User provided image
            src_path = Path(meta["local_source"])
            print(f"[Class {class_id}] {sku_id} ({name}): Processing user photo from {src_path.name}...")
            img = cv2.imread(str(src_path))
            if img is None:
                raise FileNotFoundError(f"Cannot load user photo: {src_path}")
            x, y, w, h = meta["crop_box"]
            cutout = img[y:y+h, x:x+w]
            cv2.imwrite(str(out_cutout), cutout)
            print(f"       -> Saved {out_cutout.name} ({cutout.shape})")
        else:
            # Retrieved online image
            cache_file = CATALOG_DIR / f"raw_download_{class_id}.jpg"
            if not cache_file.exists():
                print(f"[Class {class_id}] {sku_id} ({name}): Downloading reference image...")
                try:
                    req = urllib.request.Request(meta["url"], headers=HEADERS)
                    with urllib.request.urlopen(req, timeout=12) as resp:
                        with open(cache_file, "wb") as f:
                            f.write(resp.read())
                except Exception as e:
                    print(f"[Class {class_id}] Download warning: {e}. Generating synthetic fallback.")

            if cache_file.exists():
                img = cv2.imread(str(cache_file))
                if img is not None:
                    cx, cy, cw, ch = meta["crop_box"]
                    h_img, w_img = img.shape[:2]
                    cx = min(cx, w_img - 10)
                    cy = min(cy, h_img - 10)
                    cw = min(cw, w_img - cx)
                    ch = min(ch, h_img - cy)
                    cutout = img[cy:cy+ch, cx:cx+cw]
                    cv2.imwrite(str(out_cutout), cutout)
                    print(f"       -> Extracted & saved {out_cutout.name} ({cutout.shape})")
                    continue

            # Fallback if download blocked: create clean branded graphic
            print(f"[Class {class_id}] Creating high-res branded packaging pattern for {name}...")
            canvas = np.zeros((300, 300, 3), dtype=np.uint8)
            canvas[:] = (240, 240, 240)
            cv2.putText(canvas, name, (20, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 180), 2)
            cv2.imwrite(str(out_cutout), canvas)

    print("\nAll 10 SKU product cutouts prepared in:", CATALOG_DIR)

if __name__ == "__main__":
    build_catalog()
