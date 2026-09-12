import time
from pathlib import Path
from typing import Generator, Union, Tuple
import cv2
import numpy as np
from ultralytics import YOLO

class EdgeYOLODetector:
    """
    Low-level edge YOLO inference engine with:
    - Safe checkpoint loading with informative errors
    - Resilient RTSP / camera streaming with automatic reconnection
    - Universal frame generator for images, video files, webcams, and network streams
    """

    def __init__(self, model_path: Union[str, Path], confidence: float = 0.25, device: str = "cpu"):
        self.model_path = str(model_path)
        self.confidence = confidence
        self.device = device
        self.model = None
        self._load_model()

    def _load_model(self):
        if not Path(self.model_path).exists():
            raise FileNotFoundError(
                f"[EdgeYOLODetector] Model checkpoint not found at '{self.model_path}'. "
                "Please verify the model path or train a model with 'python scripts/train.py'."
            )
        try:
            self.model = YOLO(self.model_path)
            print(f"[EdgeYOLODetector] Loaded checkpoint '{self.model_path}' on device '{self.device}'.")
        except Exception as e:
            raise RuntimeError(f"[EdgeYOLODetector] Failed to initialize YOLO model from '{self.model_path}': {e}")

    @property
    def class_names(self) -> dict:
        if self.model and hasattr(self.model, "names"):
            return self.model.names
        return {}

    def predict_frame(self, frame: np.ndarray, conf: float = None) -> list:
        """Run raw inference on a single numpy frame."""
        if self.model is None or frame is None or frame.size == 0:
            return []
        effective_conf = conf if conf is not None else self.confidence
        results = self.model(frame, conf=effective_conf, device=self.device, verbose=False)
        return results

    @staticmethod
    def stream_source(
        source: Union[str, int],
        reconnect_delay: float = 2.0,
        max_reconnects: int = 10
    ) -> Generator[Tuple[bool, np.ndarray], None, None]:
        """
        Robust source iterator for webcam, video file, or RTSP stream.
        Automatically reconnects if the network stream disconnects.
        """
        is_device_idx = isinstance(source, int) or (isinstance(source, str) and source.isdigit())
        stream_src = int(source) if is_device_idx else str(source)

        reconnect_count = 0
        while reconnect_count < max_reconnects:
            cap = cv2.VideoCapture(stream_src)
            if not cap.isOpened():
                reconnect_count += 1
                print(f"[StreamSource] Could not open '{source}'. Reconnect attempt {reconnect_count}/{max_reconnects}...")
                time.sleep(reconnect_delay)
                continue

            reconnect_count = 0 # reset on successful connection
            try:
                while True:
                    ret, frame = cap.read()
                    if not ret or frame is None:
                        # Video file ended or stream disconnected
                        break
                    yield True, frame
            finally:
                cap.release()

            # If source was a local file, stop after one complete playback
            if isinstance(source, str) and Path(source).is_file():
                break

            # If it's a live camera or RTSP, attempt reconnect
            time.sleep(reconnect_delay)
            reconnect_count += 1

        yield False, None
