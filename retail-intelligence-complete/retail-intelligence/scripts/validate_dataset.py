import sys
import argparse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from collections import defaultdict
import cv2

from scripts.common import DATASETS_DIR, load_products_config

def validate_dataset(dataset_dir: str = None, config_path: str = None):
    base_dir = Path(dataset_dir) if dataset_dir else DATASETS_DIR / "products"
    try:
        products_cfg = load_products_config(config_path)
    except Exception as e:
        print(f"[Error] Failed to load products config: {e}")
        return False

    names = products_cfg.get("names", {})
    expected_nc = products_cfg.get("nc", len(names))
    valid_class_ids = set(range(expected_nc))

    print("=" * 60)
    print(" SmartRetail AI - Dataset Integrity & Quality Validator")
    print(f" Directory: {base_dir}")
    print(f" Expected Classes ({expected_nc}): {list(names.values())}")
    print("=" * 60)

    images_base = base_dir / "images"
    labels_base = base_dir / "labels"

    if not images_base.exists():
        print(f"[Warning] '{images_base}' does not exist yet.")
        print("Please place collected raw images into 'datasets/products/raw/images/' and run 'python scripts/prepare_dataset.py'.")
        return False

    splits = ["train", "val", "test"]
    total_errors = 0
    total_warnings = 0
    per_class_counts = defaultdict(lambda: defaultdict(int))
    total_images_checked = 0
    total_labels_checked = 0

    for split in splits:
        img_split_dir = images_base / split
        lbl_split_dir = labels_base / split

        if not img_split_dir.exists():
            print(f"[Notice] Split '{split}' images folder not found at {img_split_dir}")
            continue

        images = list(img_split_dir.glob("*.*"))
        print(f"\n--- Checking Split: '{split}' ({len(images)} images) ---")

        for img_path in images:
            if img_path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp", ".bmp"}:
                continue

            total_images_checked += 1

            # 1. Check if image is readable
            img = cv2.imread(str(img_path))
            if img is None or img.size == 0:
                print(f"  [ERROR] Unreadable/corrupted image: {img_path.name}")
                total_errors += 1
                continue

            # 2. Check matching label file
            label_file = lbl_split_dir / f"{img_path.stem}.txt"
            if not label_file.exists():
                print(f"  [WARNING] Missing label file for image: {img_path.name}")
                total_warnings += 1
                continue

            total_labels_checked += 1

            # 3. Parse label lines
            content = label_file.read_text(encoding="utf-8").strip()
            if not content:
                # Empty label (negative background image)
                continue

            lines = content.splitlines()
            for line_no, line in enumerate(lines, 1):
                parts = line.strip().split()
                if not parts:
                    continue
                if len(parts) != 5:
                    print(f"  [ERROR] Invalid format in {label_file.name}:{line_no} -> '{line}' (expected 5 tokens)")
                    total_errors += 1
                    continue

                try:
                    cls_id = int(parts[0])
                    xc, yc, w, h = map(float, parts[1:])
                except ValueError:
                    print(f"  [ERROR] Non-numeric token in {label_file.name}:{line_no} -> '{line}'")
                    total_errors += 1
                    continue

                # Check class ID
                if cls_id not in valid_class_ids:
                    print(f"  [ERROR] Invalid class ID {cls_id} in {label_file.name}:{line_no} (expected 0..{expected_nc-1})")
                    total_errors += 1

                # Check normalized coordinates
                if not (0.0 <= xc <= 1.0 and 0.0 <= yc <= 1.0 and 0.0 <= w <= 1.0 and 0.0 <= h <= 1.0):
                    print(f"  [ERROR] Coordinates out of [0, 1] range in {label_file.name}:{line_no}: {parts[1:]}")
                    total_errors += 1

                if w <= 0.0 or h <= 0.0:
                    print(f"  [ERROR] Zero or negative box dimension in {label_file.name}:{line_no}: w={w}, h={h}")
                    total_errors += 1

                per_class_counts[cls_id][split] += 1

    print("\n" + "=" * 60)
    print(" Per-Class Annotation Distribution Report")
    print("=" * 60)
    print(f"{'Class ID':<10} {'Class Name':<22} {'Train':<8} {'Val':<8} {'Test':<8} {'Total':<8}")
    print("-" * 60)
    for cid in range(expected_nc):
        cname = names.get(cid, f"Class_{cid}")
        c_train = per_class_counts[cid]["train"]
        c_val = per_class_counts[cid]["val"]
        c_test = per_class_counts[cid]["test"]
        c_tot = c_train + c_val + c_test
        print(f"{cid:<10} {cname:<22} {c_train:<8} {c_val:<8} {c_test:<8} {c_tot:<8}")

    print("-" * 60)
    print(f"Checked: {total_images_checked} images, {total_labels_checked} label files.")
    print(f"Results: {total_errors} Errors, {total_warnings} Warnings.")
    if total_errors == 0:
        print("[SUCCESS] Dataset passed all validation checks.")
        return True
    else:
        print(f"[FAIL] Found {total_errors} critical dataset formatting errors. Please fix before training.")
        return False

def main():
    parser = argparse.ArgumentParser(description="Validate retail SKU YOLO dataset format, bounding boxes, and class balance")
    parser.add_argument("--dataset", default="datasets/products", help="Path to products dataset root")
    parser.add_argument("--config", default="configs/products.yaml", help="Path to products.yaml config")
    args = parser.parse_args()

    is_valid = validate_dataset(args.dataset, args.config)
    sys.exit(0 if is_valid else 1)

if __name__ == "__main__":
    main()
