import os
import sys
import json
import time
import shutil
import argparse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ultralytics import YOLO

from scripts.common import (
    ROOT_DIR, CONFIGS_DIR, MODELS_DIR,
    get_device, load_products_config, load_training_config
)

def train_sku_model(
    model_name: str = None,
    data_yaml: str = None,
    epochs: int = None,
    batch: int = None,
    imgsz: int = None,
    device: str = None,
    patience: int = None,
    save_dir: str = None
):
    print("=" * 65)
    print(" SmartRetail AI - 10-SKU Transfer Learning Pipeline")
    print("=" * 65)

    training_cfg = load_training_config()
    products_cfg_path = Path(data_yaml) if data_yaml else CONFIGS_DIR / "products.yaml"
    products_cfg = load_products_config(str(products_cfg_path))

    base_model = model_name or training_cfg.get("model", "yolo11n.pt")
    num_epochs = epochs or training_cfg.get("epochs", 100)
    batch_size = batch or training_cfg.get("batch", 16)
    image_size = imgsz or training_cfg.get("imgsz", 640)
    early_stop_patience = patience or training_cfg.get("patience", 15)
    compute_device = device or get_device()

    print(f"Base Model:       {base_model}")
    print(f"Dataset YAML:     {products_cfg_path}")
    print(f"Classes ({products_cfg.get('nc', 10)}):   {list(products_cfg.get('names', {}).values())}")
    print(f"Compute Device:   {compute_device}")
    print(f"Epochs / Batch:   {num_epochs} / {batch_size} (imgsz={image_size})")
    print("-" * 65)

    # Check that dataset files exist
    dataset_root = ROOT_DIR / products_cfg.get("path", "datasets/products")
    train_images = dataset_root / products_cfg.get("train", "images/train")
    if not train_images.exists() or not any(train_images.iterdir()):
        print(f"[ERROR] No training images found in: {train_images}")
        print("Please run 'python scripts/prepare_dataset.py' with your annotated images first.")
        sys.exit(1)

    # Load YOLO base model
    print(f"[Train] Initializing transfer learning from base checkpoint: {base_model}...")
    model = YOLO(base_model)

    # Train model
    start_time = time.time()
    results = model.train(
        data=str(products_cfg_path),
        epochs=num_epochs,
        batch=batch_size,
        imgsz=image_size,
        patience=early_stop_patience,
        device=compute_device,
        workers=training_cfg.get("workers", 4),
        optimizer=training_cfg.get("optimizer", "auto"),
        lr0=training_cfg.get("lr0", 0.01),
        lrf=training_cfg.get("lrf", 0.01),
        hsv_h=training_cfg.get("hsv_h", 0.015),
        hsv_s=training_cfg.get("hsv_s", 0.7),
        hsv_v=training_cfg.get("hsv_v", 0.4),
        degrees=training_cfg.get("degrees", 10.0),
        translate=training_cfg.get("translate", 0.1),
        scale=training_cfg.get("scale", 0.5),
        fliplr=training_cfg.get("fliplr", 0.5),
        flipud=training_cfg.get("flipud", 0.0),
        mosaic=training_cfg.get("mosaic", 1.0),
        project=str(MODELS_DIR / "training_runs"),
        name="sku_run",
        exist_ok=True
    )

    elapsed_time = time.time() - start_time
    print(f"\n[Train] Training complete in {elapsed_time / 60:.1f} minutes!")

    # Locate best checkpoint and copy to models/trained/
    trained_dir = Path(save_dir) if save_dir else MODELS_DIR / "trained"
    trained_dir.mkdir(parents=True, exist_ok=True)

    # Search for weights in save_dir or model.trainer.save_dir
    save_run_dir = getattr(model.trainer, "save_dir", MODELS_DIR / "training_runs" / "sku_run")
    best_pt = Path(save_run_dir) / "weights" / "best.pt"
    last_pt = Path(save_run_dir) / "weights" / "last.pt"

    dest_best = trained_dir / "best.pt"
    dest_last = trained_dir / "last.pt"

    if best_pt.exists():
        shutil.copy2(best_pt, dest_best)
        print(f"[Train] Checkpoint saved: {dest_best}")
    if last_pt.exists():
        shutil.copy2(last_pt, dest_last)

    # Save model metadata.json for versioning and verification
    metadata = {
        "model_type": "YOLO11_Retail_SKU",
        "base_model": base_model,
        "classes": products_cfg.get("names", {}),
        "sku_ids": products_cfg.get("sku_ids", {}),
        "nc": products_cfg.get("nc", len(products_cfg.get("names", {}))),
        "epochs": num_epochs,
        "batch_size": batch_size,
        "imgsz": image_size,
        "training_duration_seconds": round(elapsed_time, 2),
        "training_device": compute_device,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }

    meta_file = trained_dir / "metadata.json"
    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
    print(f"[Train] Metadata logged to: {meta_file}")
    print("\n[SUCCESS] Model ready for deployment! You can run:")
    print(f"  python scripts/evaluate.py --model {dest_best}")
    print(f"  python scripts/predict.py --model {dest_best} --source <image_or_video>")

def main():
    parser = argparse.ArgumentParser(description="Train custom 10-SKU retail object detector")
    parser.add_argument("--model", default="yolo11n.pt", help="Base checkpoint (yolo11n.pt, yolo11s.pt, etc.)")
    parser.add_argument("--data", default="configs/products.yaml", help="Path to products.yaml")
    parser.add_argument("--epochs", type=int, default=None, help="Number of training epochs")
    parser.add_argument("--batch", type=int, default=None, help="Batch size")
    parser.add_argument("--imgsz", type=int, default=None, help="Image resolution size (640)")
    parser.add_argument("--device", default=None, help="Device to use ('cpu', '0', 'cuda')")
    parser.add_argument("--patience", type=int, default=None, help="Early stopping patience")
    parser.add_argument("--save-dir", default="models/trained", help="Directory to save final model checkpoint")
    args = parser.parse_args()

    train_sku_model(
        model_name=args.model,
        data_yaml=args.data,
        epochs=args.epochs,
        batch=args.batch,
        imgsz=args.imgsz,
        device=args.device,
        patience=args.patience,
        save_dir=args.save_dir
    )

if __name__ == "__main__":
    main()
