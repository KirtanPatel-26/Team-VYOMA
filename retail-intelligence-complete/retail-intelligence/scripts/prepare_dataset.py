import os
import shutil
import random
import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from collections import defaultdict

from scripts.common import DATASETS_DIR

def get_session_id(filename: str) -> str:
    """
    Extract session identifier from filename.
    Format: '<session_prefix>_<frame_id>.jpg' -> '<session_prefix>'
    If no underscore, uses the full stem.
    """
    stem = Path(filename).stem
    if "_" in stem:
        parts = stem.rsplit("_", 1)
        return parts[0]
    return stem

def prepare_dataset(
    raw_dir: str = None,
    dest_dir: str = None,
    train_ratio: float = 0.70,
    val_ratio: float = 0.20,
    test_ratio: float = 0.10,
    seed: int = 42
):
    random.seed(seed)

    base_raw = Path(raw_dir) if raw_dir else DATASETS_DIR / "products" / "raw"
    base_dest = Path(dest_dir) if dest_dir else DATASETS_DIR / "products"

    raw_images_dir = base_raw / "images"
    raw_labels_dir = base_raw / "labels"

    if not raw_images_dir.exists():
        print(f"[Warning] Raw images folder not found: {raw_images_dir}")
        print("Creating template directory structure in datasets/products/raw/{images, labels}...")
        raw_images_dir.mkdir(parents=True, exist_ok=True)
        raw_labels_dir.mkdir(parents=True, exist_ok=True)
        return

    # Find all images
    valid_exts = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
    image_files = [f for f in raw_images_dir.iterdir() if f.suffix.lower() in valid_exts]

    if not image_files:
        print(f"[Notice] No images found in {raw_images_dir}. Populate this directory with annotated images.")
        # Create target directories so structure is ready
        for split in ["train", "val", "test"]:
            (base_dest / "images" / split).mkdir(parents=True, exist_ok=True)
            (base_dest / "labels" / split).mkdir(parents=True, exist_ok=True)
        return

    print(f"[Dataset] Found {len(image_files)} raw images. Grouping by recording session...")

    # Group by session prefix
    session_map = defaultdict(list)
    for img in image_files:
        session = get_session_id(img.name)
        session_map[session].append(img)

    sessions = list(session_map.keys())
    random.shuffle(sessions)
    print(f"[Dataset] Identified {len(sessions)} distinct session groups: {sessions[:5]}{'...' if len(sessions) > 5 else ''}")

    # Allocate sessions to train, val, test
    train_images = []
    val_images = []
    test_images = []

    if len(sessions) >= 3:
        # Session-level partitioning to guarantee zero train/val/test data leakage
        n_train = max(1, int(len(sessions) * train_ratio))
        n_val = max(1, int(len(sessions) * val_ratio))
        
        train_sessions = set(sessions[:n_train])
        val_sessions = set(sessions[n_train:n_train + n_val])
        test_sessions = set(sessions[n_train + n_val:])
        if not test_sessions and len(sessions) >= 3:
            test_sessions = {sessions[-1]}
            train_sessions.discard(sessions[-1])

        for sess, imgs in session_map.items():
            if sess in train_sessions:
                train_images.extend(imgs)
            elif sess in val_sessions:
                val_images.extend(imgs)
            else:
                test_images.extend(imgs)
    else:
        # Fallback when single session / flat directory: frame-level random split
        all_imgs = list(image_files)
        random.shuffle(all_imgs)
        n_train = int(len(all_imgs) * train_ratio)
        n_val = int(len(all_imgs) * val_ratio)
        train_images = all_imgs[:n_train]
        val_images = all_imgs[n_train:n_train + n_val]
        test_images = all_imgs[n_train + n_val:]

    # Create destination directories
    splits = {
        "train": train_images,
        "val": val_images,
        "test": test_images
    }

    for split_name, files in splits.items():
        img_out = base_dest / "images" / split_name
        lbl_out = base_dest / "labels" / split_name
        img_out.mkdir(parents=True, exist_ok=True)
        lbl_out.mkdir(parents=True, exist_ok=True)

        copied = 0
        labels_found = 0
        for img_path in files:
            dest_img = img_out / img_path.name
            shutil.copy2(img_path, dest_img)
            copied += 1

            # Look for matching YOLO label .txt
            label_file = raw_labels_dir / f"{img_path.stem}.txt"
            dest_lbl = lbl_out / f"{img_path.stem}.txt"
            if label_file.exists():
                shutil.copy2(label_file, dest_lbl)
                labels_found += 1
            else:
                # Write empty annotation file if no bounding boxes present in image
                dest_lbl.touch()

        print(f"  -> Split '{split_name}': {copied} images, {labels_found} label files copied.")

    print(f"[Dataset] Partitioning complete! Images stored in: {base_dest}/images/")

def main():
    parser = argparse.ArgumentParser(description="Partition raw retail dataset into leakage-safe 70/20/10 splits")
    parser.add_argument("--raw", default="datasets/products/raw", help="Raw dataset root folder")
    parser.add_argument("--dest", default="datasets/products", help="Destination folder for train/val/test")
    parser.add_argument("--train-ratio", type=float, default=0.70)
    parser.add_argument("--val-ratio", type=float, default=0.20)
    parser.add_argument("--test-ratio", type=float, default=0.10)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    prepare_dataset(
        raw_dir=args.raw,
        dest_dir=args.dest,
        train_ratio=args.train_ratio,
        val_ratio=args.val_ratio,
        test_ratio=args.test_ratio,
        seed=args.seed
    )

if __name__ == "__main__":
    main()
