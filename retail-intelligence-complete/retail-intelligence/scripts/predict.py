import os
import sys
import json
import time
import argparse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import cv2
from ultralytics import YOLO

from scripts.common import ROOT_DIR, REPORTS_DIR, load_products_config

def run_predict(
    source: str,
    model_path: str = "models/trained/best.pt",
    conf: float = 0.5,
    save_dir: str = "reports/predictions",
    show: bool = False
):
    print("=" * 60)
    print(" SmartRetail AI - Model Inference CLI")
    print(f" Source: {source} | Model: {model_path} | Conf: {conf}")
    print("=" * 60)

    model_file = Path(model_path)
    if not model_file.exists():
        raise FileNotFoundError(f"Model weights not found at: {model_path}")

    out_path = Path(save_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    products_cfg = load_products_config()
    names = products_cfg.get("names", {})
    sku_ids = products_cfg.get("sku_ids", {})

    model = YOLO(str(model_file))

    # Determine source type
    is_webcam = source.isdigit()
    source_val = int(source) if is_webcam else source

    results = model(source_val, conf=conf, stream=True)
    all_detections_log = []
    frame_idx = 0

    for r in results:
        frame_idx += 1
        frame_dets = []
        im = r.orig_img.copy()

        if r.boxes is not None:
            for b in r.boxes:
                cls_id = int(b.cls[0])
                confidence = float(b.conf[0])
                x1, y1, x2, y2 = map(int, b.xyxy[0].tolist())

                pname = names.get(cls_id, f"Class_{cls_id}")
                sku = sku_ids.get(cls_id, f"SKU{cls_id+1:03d}")

                label = f"{sku}: {pname} {confidence:.2f}"
                cv2.rectangle(im, (x1, y1), (x2, y2), (0, 255, 120), 2)
                cv2.rectangle(im, (x1, max(0, y1 - 20)), (x1 + len(label) * 8 + 10, y1), (0, 255, 120), -1)
                cv2.putText(im, label, (x1 + 4, max(14, y1 - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1)

                frame_dets.append({
                    "frame": frame_idx,
                    "sku_id": sku,
                    "product_name": pname,
                    "confidence": round(confidence, 3),
                    "bbox": [x1, y1, x2, y2]
                })

        all_detections_log.extend(frame_dets)

        if not is_webcam and frame_idx == 1 and Path(source).is_file():
            # Save single image result
            save_file = out_path / f"pred_{Path(source).name}"
            cv2.imwrite(str(save_file), im)
            print(f"[Predict] Saved output visualization to: {save_file}")

        if show:
            cv2.imshow("SmartRetail SKU Detector", im)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        if not is_webcam and frame_idx >= 1 and Path(source).suffix.lower() in {".jpg", ".jpeg", ".png"}:
            break

    if show:
        cv2.destroyAllWindows()

    # Save detections log JSON
    log_file = out_path / f"detections_{int(time.time())}.json"
    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(all_detections_log, f, indent=2)
    print(f"[Predict] Processed {frame_idx} frame(s), {len(all_detections_log)} detections logged to: {log_file}")

def main():
    parser = argparse.ArgumentParser(description="Run YOLO SKU inference on image, video, or webcam")
    parser.add_argument("--source", required=True, help="Image file, video file, RTSP URL, or webcam index ('0')")
    parser.add_argument("--model", default="models/trained/best.pt", help="Path to trained weights checkpoint")
    parser.add_argument("--conf", type=float, default=0.5, help="Confidence threshold")
    parser.add_argument("--save-dir", default="reports/predictions", help="Directory to save annotated outputs")
    parser.add_argument("--show", action="store_true", help="Display desktop preview window")
    args = parser.parse_args()

    run_predict(
        source=args.source,
        model_path=args.model,
        conf=args.conf,
        save_dir=args.save_dir,
        show=args.show
    )

if __name__ == "__main__":
    main()
