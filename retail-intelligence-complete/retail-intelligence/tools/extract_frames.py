import argparse
from pathlib import Path
import cv2

parser = argparse.ArgumentParser()
parser.add_argument("--video", required=True)
parser.add_argument("--output", default="datasets/images")
parser.add_argument("--every", type=int, default=30)
args = parser.parse_args()

out = Path(args.output)
out.mkdir(parents=True, exist_ok=True)

cap = cv2.VideoCapture(args.video)
i = 0
saved = 0

while True:
    ok, frame = cap.read()
    if not ok:
        break

    if i % args.every == 0:
        cv2.imwrite(str(out / f"frame_{saved:05d}.jpg"), frame)
        saved += 1

    i += 1

cap.release()
print(f"Saved {saved} frames to {out}")
