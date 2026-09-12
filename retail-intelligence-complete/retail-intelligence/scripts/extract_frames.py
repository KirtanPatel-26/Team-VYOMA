import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import cv2
import numpy as np

from scripts.common import ROOT_DIR

def frame_difference_mse(frame_a: np.ndarray, frame_b: np.ndarray) -> float:
    """Calculate Mean Squared Error between two downsampled grayscale frames."""
    gray_a = cv2.cvtColor(cv2.resize(frame_a, (64, 36)), cv2.COLOR_BGR2GRAY)
    gray_b = cv2.cvtColor(cv2.resize(frame_b, (64, 36)), cv2.COLOR_BGR2GRAY)
    return float(np.mean((gray_a.astype("float") - gray_b.astype("float")) ** 2))

def extract_frames(
    video_path: str,
    output_dir: str,
    interval: int = 10,
    prefix: str = "frame",
    resize: tuple = None,
    min_mse: float = 12.0
):
    video_file = Path(video_path)
    if not video_file.exists():
        raise FileNotFoundError(f"Video file does not exist: {video_path}")

    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(str(video_file))
    if not cap.isOpened():
        raise RuntimeError(f"Failed to open video source: {video_path}")

    total_video_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    print(f"[Extract] Opening '{video_file.name}' | Total Frames: {total_video_frames} | FPS: {fps:.1f}")

    frame_idx = 0
    saved_count = 0
    skipped_near_dup = 0
    last_saved_frame = None

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_idx % interval == 0:
            # Check near-duplicate
            if last_saved_frame is not None and min_mse > 0:
                mse = frame_difference_mse(frame, last_saved_frame)
                if mse < min_mse:
                    skipped_near_dup += 1
                    frame_idx += 1
                    continue

            if resize:
                frame_to_save = cv2.resize(frame, resize)
            else:
                frame_to_save = frame

            filename = f"{prefix}_{saved_count:05d}.jpg"
            save_file = out_path / filename
            cv2.imwrite(str(save_file), frame_to_save, [cv2.IMWRITE_JPEG_QUALITY, 95])
            last_saved_frame = frame.copy()
            saved_count += 1

        frame_idx += 1

    cap.release()
    print(f"[Extract] Complete! Saved: {saved_count} frames to '{out_path}' (Skipped {skipped_near_dup} near-duplicates).")

def main():
    parser = argparse.ArgumentParser(description="Extract video frames with duplicate filtering for dataset annotation")
    parser.add_argument("--input", required=True, help="Input video file path")
    parser.add_argument("--output", default="datasets/products/raw/images", help="Target output folder for frames")
    parser.add_argument("--interval", type=int, default=10, help="Frame sample rate (extract every Nth frame)")
    parser.add_argument("--prefix", default="session1", help="File prefix (used to group frames by session and prevent train/test leakage)")
    parser.add_argument("--resize", type=str, default="", help="Optional resize WxH (e.g. 1280x720)")
    parser.add_argument("--min-mse", type=float, default=10.0, help="Minimum MSE threshold to filter near-duplicate static frames")
    args = parser.parse_args()

    resize_tuple = None
    if args.resize and "x" in args.resize:
        w, h = map(int, args.resize.lower().split("x"))
        resize_tuple = (w, h)

    extract_frames(
        video_path=args.input,
        output_dir=args.output,
        interval=args.interval,
        prefix=args.prefix,
        resize=resize_tuple,
        min_mse=args.min_mse
    )

if __name__ == "__main__":
    main()
