import sys
import argparse
import cv2

from app.camera.video import VideoCamera
from app.config.settings import CAMERA_SOURCE, YOLO_MODEL, CONFIDENCE
from app.detection.detector import ObjectDetector
from app.detection.tracker import CentroidTracker
from app.products.matcher import ProductMatcher
from app.products.recognizer import ProductRecognizer

def run_desktop_preview(source=None):
    cam_source = source if source is not None else CAMERA_SOURCE
    print("=" * 60)
    print(" SmartRetail AI - Edge Inference CCTV Engine")
    print(f" Source: {cam_source} | Model: YOLOv11")
    print(" Press 'q' in the video window to stop.")
    print("=" * 60)

    camera = VideoCamera(cam_source)
    detector = ObjectDetector(YOLO_MODEL, CONFIDENCE)
    detector.set_active_source(cam_source)
    print(f" Detector Mode: {detector.mode}")
    tracker = CentroidTracker()
    recognizer = ProductRecognizer(ProductMatcher({}))

    try:
        for frame in camera.frames():
            detections = detector.detect(frame)
            detections = tracker.update(detections)
            detections = recognizer.recognize(detections)

            for d in detections:
                x1, y1, x2, y2 = d.bbox
                if d.class_name == "person":
                    label = f"Shopper #{d.track_id} (Dwell: {tracker.get_dwell_time(d.track_id):.0f}s)"
                    color = (255, 100, 0)
                else:
                    sku_tag = f"[{d.sku_id}] " if getattr(d, 'sku_id', None) else ""
                    label = f"{sku_tag}{d.product_name or d.class_name} {d.confidence:.2f}"
                    color = (0, 255, 100)

                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                cv2.putText(
                    frame, label, (x1, max(20, y1 - 8)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2
                )

            cv2.imshow("SmartRetail AI - Edge Vision Pipeline", frame)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        camera.release()
        cv2.destroyAllWindows()

def run_web_dashboard(port=8000, reload=False):
    import uvicorn
    print("=" * 60)
    print(f" Launching SmartRetail Operations Hub at http://127.0.0.1:{port}")
    print("=" * 60)
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=reload)

def main():
    parser = argparse.ArgumentParser(description="SmartRetail Edge AI Platform")
    parser.add_argument("--preview", action="store_true", help="Launch OpenCV desktop window")
    parser.add_argument("--camera", type=str, default=None, help="Camera index (e.g. 0 for internal, 1 for external USB webcam)")
    parser.add_argument("--port", type=int, default=8000, help="Web dashboard port (default: 8000)")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for FastAPI server")
    args = parser.parse_args()

    if args.preview:
        run_desktop_preview(source=args.camera)
    else:
        if args.camera is not None:
            import os
            os.environ["CAMERA_SOURCE"] = str(args.camera)
        run_web_dashboard(port=args.port, reload=args.reload)

if __name__ == "__main__":
    main()
