import cv2
import time
import threading
from pathlib import Path

def scan_available_cameras(max_devices=4):
    """
    Scans hardware camera indices (0 to max_devices-1) to detect active webcams.
    Returns a list of dicts with device index, resolution, and descriptive label.
    """
    cameras = []
    for idx in range(max_devices):
        cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap = cv2.VideoCapture(idx)

        if cap.isOpened():
            ret, frame = cap.read()
            if ret and frame is not None:
                w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or frame.shape[1])
                h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or frame.shape[0])
                fps_val = cap.get(cv2.CAP_PROP_FPS) or 30.0
                dev_type = "Integrated / Primary" if idx == 0 else f"External USB Camera"
                cameras.append({
                    "index": idx,
                    "label": f"Camera {idx}: {dev_type} ({w}x{h})",
                    "width": w,
                    "height": h,
                    "fps": round(fps_val, 1)
                })
            cap.release()

    return cameras

class VideoCamera:
    """
    Continuous thread-safe video camera stream.
    Supports looping local retail video files, webcams (0, 1, 2...), and RTSP CCTV feeds.
    """
    def __init__(self, source):
        self.source = source
        self.is_numeric = isinstance(source, int) or (isinstance(source, str) and str(source).strip().isdigit())
        self.cap = None
        self.lock = threading.Lock()
        self.running = True
        self.last_frame = None
        self.fps = 30
        self.width = 1280
        self.height = 720
        self.has_looped = False
        
        self._open_stream()

    def _open_stream(self):
        if self.cap is not None:
            self.cap.release()
            self.cap = None

        if self.is_numeric:
            src = int(self.source)
            self.cap = cv2.VideoCapture(src, cv2.CAP_DSHOW)
            if not self.cap.isOpened():
                self.cap = cv2.VideoCapture(src)
            
            if self.cap.isOpened():
                # Configure resolution and reduce buffer lag for live USB feeds
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
                self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 1280)
                self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 720)
        else:
            src_str = str(self.source)
            self.cap = cv2.VideoCapture(src_str)
            if not self.cap.isOpened():
                alt_path = Path("videos/store.mp4")
                if alt_path.exists():
                    self.cap = cv2.VideoCapture(str(alt_path))

        if self.cap is not None and self.cap.isOpened():
            val = self.cap.get(cv2.CAP_PROP_FPS)
            if val and val > 0:
                self.fps = min(60.0, max(15.0, val))

    def set_source(self, new_source):
        with self.lock:
            if self.cap is not None:
                self.cap.release()
                self.cap = None
            self.source = new_source
            self.is_numeric = isinstance(new_source, int) or (isinstance(new_source, str) and str(new_source).strip().isdigit())
            self.last_frame = None
            self._open_stream()
            return self.cap is not None and self.cap.isOpened()

    def get_source_info(self):
        return {
            "source": str(self.source),
            "is_webcam": self.is_numeric,
            "fps": round(self.fps, 1),
            "width": self.width,
            "height": self.height,
            "is_opened": self.cap is not None and self.cap.isOpened()
        }

    def get_frame(self):
        with self.lock:
            if not self.cap or not self.cap.isOpened():
                self._open_stream()
                if not self.cap or not self.cap.isOpened():
                    return None

            ok, frame = self.cap.read()
            if not ok:
                # If file video ended, loop seamlessly back to start
                if not self.is_numeric:
                    self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    self.has_looped = True
                    ok, frame = self.cap.read()
                
            if ok:
                self.last_frame = frame
                return frame
            return self.last_frame

    def frames(self):
        while self.running:
            frame = self.get_frame()
            if frame is not None:
                yield frame
            time.sleep(1.0 / self.fps)

    def release(self):
        self.running = False
        with self.lock:
            if self.cap:
                self.cap.release()
