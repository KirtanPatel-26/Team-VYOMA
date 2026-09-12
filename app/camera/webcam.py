import cv2


class Webcam:
    def __init__(self, index=0):
        self.cap = cv2.VideoCapture(index)
        if not self.cap.isOpened():
            raise RuntimeError(f"Unable to open webcam index {index}")

    def frames(self):
        while True:
            ok, frame = self.cap.read()
            if not ok:
                break
            yield frame

    def release(self):
        self.cap.release()
