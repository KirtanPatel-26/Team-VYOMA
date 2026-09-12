import os
import random
import math
from pathlib import Path
import cv2
import numpy as np

ROOT_DIR = Path(__file__).resolve().parents[1]
CATALOG_DIR = ROOT_DIR / "datasets" / "products" / "raw" / "catalog"
DATASET_DIR = ROOT_DIR / "datasets" / "products"

SKU_METADATA = {
    0: ("SKU001", "Fanta Orange"),
    1: ("SKU002", "Pringles Original"),
    2: ("SKU003", "Oreo"),
    3: ("SKU004", "Amul Taaza"),
    4: ("SKU005", "Real Orange Juice"),
    5: ("SKU006", "Dove Soap"),
    6: ("SKU007", "Coca Cola"),
    7: ("SKU008", "Lays Classic"),
    8: ("SKU009", "Dairy Milk"),
    9: ("SKU010", "Colgate Paste"),
}

def load_product_cutouts():
    cutouts = {}
    for cid in range(10):
        sku_id, name = SKU_METADATA[cid]
        stem = f"sku_{cid:02d}_{sku_id}_{name.replace(' ', '_').lower()}.png"
        path = CATALOG_DIR / stem
        if not path.exists():
            raise FileNotFoundError(f"Missing cutout: {path}")
        img = cv2.imread(str(path))
        cutouts[cid] = img
    return cutouts

def generate_background(width=640, height=640, bg_type=None):
    if bg_type is None:
        bg_type = random.choice(["wood", "shelf", "store_counter", "neutral_desk", "gradient"])

    bg = np.zeros((height, width, 3), dtype=np.uint8)

    if bg_type == "wood":
        # Dark wood table surface (like the user's photos)
        base_color = np.array([random.randint(18, 28), random.randint(28, 42), random.randint(45, 65)], dtype=np.float32)
        grain = np.random.normal(0, 7, (height, width, 3))
        # Horizontal wood grain streaks
        streaks = np.sin(np.linspace(0, 15, height))[:, None, None] * 8
        bg = np.clip(base_color + grain + streaks, 10, 85).astype(np.uint8)

    elif bg_type == "shelf":
        # Retail shelf with shelf rows
        bg[:] = [random.randint(210, 235), random.randint(215, 235), random.randint(220, 240)]
        # Add shelf edge line
        shelf_y = int(height * 0.72)
        cv2.rectangle(bg, (0, shelf_y), (width, shelf_y + 24), (160, 160, 160), -1)
        cv2.rectangle(bg, (0, shelf_y + 24), (width, height), (130, 130, 130), -1)

    elif bg_type == "store_counter":
        # Light grey / beige laminate countertop
        base = [random.randint(190, 210), random.randint(190, 210), random.randint(190, 210)]
        noise = np.random.normal(0, 5, (height, width, 3))
        bg = np.clip(base + noise, 170, 230).astype(np.uint8)

    elif bg_type == "neutral_desk":
        # Office / home desk
        top_color = np.array([random.randint(180, 220), random.randint(180, 220), random.randint(180, 220)])
        bottom_color = np.array([random.randint(100, 140), random.randint(100, 140), random.randint(100, 140)])
        for y in range(height):
            alpha = y / height
            bg[y, :] = (1 - alpha) * top_color + alpha * bottom_color

    else:
        # Subtle gradient
        c1 = [random.randint(40, 120), random.randint(40, 120), random.randint(40, 120)]
        c2 = [random.randint(140, 210), random.randint(140, 210), random.randint(140, 210)]
        for y in range(height):
            ratio = y / height
            bg[y, :] = [int(c1[i] * (1 - ratio) + c2[i] * ratio) for i in range(3)]

    return bg

def augment_cutout(patch, max_angle=22, scale_range=(0.7, 1.3), lighting=True):
    h, w = patch.shape[:2]

    # 1. Random rotation
    angle = random.uniform(-max_angle, max_angle)
    center = (w / 2, h / 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    cos = np.abs(M[0, 0])
    sin = np.abs(M[0, 1])
    new_w = int((h * sin) + (w * cos))
    new_h = int((h * cos) + (w * sin))
    M[0, 2] += (new_w / 2) - center[0]
    M[1, 2] += (new_h / 2) - center[1]
    rotated = cv2.warpAffine(patch, M, (new_w, new_h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0))

    # Mask of the rotated item
    mask = cv2.warpAffine(np.ones((h, w), dtype=np.uint8) * 255, M, (new_w, new_h), flags=cv2.INTER_NEAREST, borderMode=cv2.BORDER_CONSTANT, borderValue=0)

    # 2. Lighting / brightness / contrast
    if lighting:
        alpha = random.uniform(0.75, 1.25)
        beta = random.uniform(-25, 25)
        rotated = cv2.convertScaleAbs(rotated, alpha=alpha, beta=beta)

    # 3. Scale
    scale = random.uniform(scale_range[0], scale_range[1])
    final_w = max(24, int(new_w * scale))
    final_h = max(24, int(new_h * scale))
    scaled_patch = cv2.resize(rotated, (final_w, final_h), interpolation=cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LINEAR)
    scaled_mask = cv2.resize(mask, (final_w, final_h), interpolation=cv2.INTER_NEAREST)

    return scaled_patch, scaled_mask

def blend_object_onto_bg(bg, patch, mask, x, y):
    h_bg, w_bg = bg.shape[:2]
    h_p, w_p = patch.shape[:2]

    # Clip coordinates
    x1, y1 = max(0, x), max(0, y)
    x2, y2 = min(w_bg, x + w_p), min(h_bg, y + h_p)

    if x2 <= x1 or y2 <= y1:
        return None

    px1 = x1 - x
    py1 = y1 - y
    px2 = px1 + (x2 - x1)
    py2 = py1 + (y2 - y1)

    p_crop = patch[py1:py2, px1:px2]
    m_crop = mask[py1:py2, px1:px2]

    # Normalize mask to [0, 1]
    m_float = (m_crop.astype(np.float32) / 255.0)[:, :, None]

    # Soften edges slightly
    m_float = cv2.GaussianBlur(m_float, (3, 3), 0)[:, :, None] if m_float.ndim == 2 else cv2.GaussianBlur(m_float, (3, 3), 0)[:, :, None]

    bg_roi = bg[y1:y2, x1:x2].astype(np.float32)
    p_float = p_crop.astype(np.float32)

    blended = (p_float * m_float) + (bg_roi * (1.0 - m_float))
    bg[y1:y2, x1:x2] = np.clip(blended, 0, 255).astype(np.uint8)

    # Return actual bounding box
    return (x1, y1, x2, y2)

def generate_dataset(num_train=160, num_val=40, num_test=20):
    print("=" * 65)
    print(" Generating Synthetic Multi-View Dataset for 10 Retail SKUs")
    print("=" * 65)

    cutouts = load_product_cutouts()

    splits = [
        ("train", num_train),
        ("val", num_val),
        ("test", num_test),
    ]

    for split_name, count in splits:
        img_dir = DATASET_DIR / "images" / split_name
        lbl_dir = DATASET_DIR / "labels" / split_name
        img_dir.mkdir(parents=True, exist_ok=True)
        lbl_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n[Split: {split_name}] Generating {count} synthetic scenes...")

        for idx in range(count):
            canvas_w, canvas_h = 640, 640
            bg = generate_background(canvas_w, canvas_h)

            boxes = [] # (class_id, x1, y1, x2, y2)

            # Determine scene type:
            # 40% single-item close-up (like webcam holding or placing Colgate / Dove)
            # 60% multi-item shelf/counter (2 to 5 items)
            is_single_item = (idx % 5 < 2)

            if is_single_item:
                # Prioritize classes 9 (Colgate) and 5 (Dove) in 40% of single items
                if random.random() < 0.4:
                    cid = random.choice([5, 9])
                else:
                    cid = random.randint(0, 9)

                patch = cutouts[cid]
                # Scale so it takes 35% to 70% of screen dimension, preserving aspect ratio
                max_dim = max(patch.shape[0], patch.shape[1])
                target_dim = random.uniform(220, 420)
                scale = target_dim / max_dim
                aug_patch, aug_mask = augment_cutout(patch, max_angle=20, scale_range=(scale*0.85, scale*1.15))

                pw, ph = aug_patch.shape[1], aug_patch.shape[0]
                pos_x = random.randint(max(10, (canvas_w - pw)//4), max(10, min(canvas_w - pw - 10, int((canvas_w - pw)*0.75))))
                pos_y = random.randint(max(10, (canvas_h - ph)//4), max(10, min(canvas_h - ph - 10, int((canvas_h - ph)*0.75))))

                bbox = blend_object_onto_bg(bg, aug_patch, aug_mask, pos_x, pos_y)
                if bbox:
                    boxes.append((cid, *bbox))

            else:
                # Multi-product shelf scene
                num_items = random.randint(2, 5)
                chosen_classes = random.sample(range(10), num_items)

                # Arrange across horizontal shelf line
                shelf_y = random.randint(int(canvas_h * 0.45), int(canvas_h * 0.68))
                x_cursor = random.randint(15, 60)

                for cid in chosen_classes:
                    patch = cutouts[cid]
                    max_dim = max(patch.shape[0], patch.shape[1])
                    target_dim = random.uniform(140, 230)
                    scale = target_dim / max_dim
                    aug_patch, aug_mask = augment_cutout(patch, max_angle=10, scale_range=(scale*0.9, scale*1.1))

                    pw, ph = aug_patch.shape[1], aug_patch.shape[0]
                    pos_x = x_cursor
                    pos_y = shelf_y - ph + random.randint(-15, 20)
                    pos_y = max(10, min(canvas_h - ph - 10, pos_y))

                    bbox = blend_object_onto_bg(bg, aug_patch, aug_mask, pos_x, pos_y)
                    if bbox:
                        boxes.append((cid, *bbox))

                    x_cursor += int(pw * random.uniform(0.85, 1.25))
                    if x_cursor > canvas_w - 60:
                        break

            # Add gentle camera noise
            if random.random() < 0.5:
                noise = np.random.normal(0, random.uniform(1, 4), bg.shape).astype(np.int16)
                bg = np.clip(bg.astype(np.int16) + noise, 0, 255).astype(np.uint8)

            img_filename = f"scene_{split_name}_{idx:04d}.jpg"
            lbl_filename = f"scene_{split_name}_{idx:04d}.txt"

            img_path = img_dir / img_filename
            lbl_path = lbl_dir / lbl_filename

            cv2.imwrite(str(img_path), bg)

            # Write YOLO labels
            with open(lbl_path, "w", encoding="utf-8") as f:
                for cid, bx1, by1, bx2, by2 in boxes:
                    # Filter tiny or invalid boxes
                    bw = bx2 - bx1
                    bh = by2 - by1
                    if bw < 16 or bh < 16:
                        continue
                    cx = (bx1 + bx2) / 2.0 / canvas_w
                    cy = (by1 + by2) / 2.0 / canvas_h
                    norm_w = bw / canvas_w
                    norm_h = bh / canvas_h

                    # Clip to [0, 1]
                    cx = max(0.0, min(1.0, cx))
                    cy = max(0.0, min(1.0, cy))
                    norm_w = max(0.0, min(1.0, norm_w))
                    norm_h = max(0.0, min(1.0, norm_h))

                    f.write(f"{cid} {cx:.6f} {cy:.6f} {norm_w:.6f} {norm_h:.6f}\n")

        print(f"[OK] Completed {count} images and labels for split '{split_name}'.")

        # Inject authentic user photo samples directly into train and val
        colgate_src = r"C:\Users\kirtan patel\.gemini\antigravity\brain\b0e944d2-a089-440e-80f7-a26962e2fcc6\.user_uploaded\media_1789202613498.jpg"
        dove_src = r"C:\Users\kirtan patel\.gemini\antigravity\brain\b0e944d2-a089-440e-80f7-a26962e2fcc6\.user_uploaded\media_1789202618794.jpg"

        c_img = cv2.imread(colgate_src)
        d_img = cv2.imread(dove_src)

        n_user_samples = 16 if split_name == "train" else 4
        for u_idx in range(n_user_samples):
            # 1. Colgate sample
            colgate_aug = cv2.resize(c_img, (640, 640))
            if random.random() < 0.5:
                colgate_aug = cv2.flip(colgate_aug, 1)
            alpha = random.uniform(0.85, 1.15)
            beta = random.uniform(-20, 20)
            colgate_aug = cv2.convertScaleAbs(colgate_aug, alpha=alpha, beta=beta)
            cv2.imwrite(str(img_dir / f"user_colgate_{u_idx:03d}.jpg"), colgate_aug)
            with open(lbl_dir / f"user_colgate_{u_idx:03d}.txt", "w") as f:
                # Colgate box normalized on 640x640:
                f.write("9 0.4837 0.5385 0.8685 0.1631\n")

            # 2. Dove sample
            dove_aug = cv2.resize(d_img, (640, 640))
            if random.random() < 0.5:
                dove_aug = cv2.flip(dove_aug, 1)
            alpha = random.uniform(0.85, 1.15)
            beta = random.uniform(-20, 20)
            dove_aug = cv2.convertScaleAbs(dove_aug, alpha=alpha, beta=beta)
            cv2.imwrite(str(img_dir / f"user_dove_{u_idx:03d}.jpg"), dove_aug)
            with open(lbl_dir / f"user_dove_{u_idx:03d}.txt", "w") as f:
                # Dove box normalized on 640x640:
                f.write("5 0.5046 0.6035 0.6966 0.4102\n")

    print("\n" + "=" * 65)
    print(" Dataset generation complete!")
    print("=" * 65)

if __name__ == "__main__":
    generate_dataset(num_train=160, num_val=40, num_test=20)
