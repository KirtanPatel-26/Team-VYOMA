from typing import Optional, Dict, Any
from app.camera.video import VideoCamera
from app.security.encryption import decrypt_data, is_encrypted
from app.security.sanitizer import sanitize_rtsp_url


class CCTVStream(VideoCamera):
    """
    Production-grade RTSP/HTTP CCTV source using OpenCV VideoCapture.
    Supports secure encrypted credentials, runtime decryption in memory,
    and automatic masking of credentials from external callers/APIs.
    """

    def __init__(
        self,
        source: str,
        camera_id: Optional[str] = None,
        camera_name: Optional[str] = None,
        username_encrypted: Optional[str] = None,
        password_encrypted: Optional[str] = None,
    ):
        self.camera_id = camera_id or "CAM_01"
        self.camera_name = camera_name or "Retail CCTV Feed"
        self._username_encrypted = username_encrypted
        self._password_encrypted = password_encrypted
        
        # If source is an encrypted token, decrypt it
        effective_source = source
        if is_encrypted(source):
            try:
                decrypted = decrypt_data(source)
                if decrypted:
                    effective_source = decrypted
            except Exception:
                pass
        
        # If separate encrypted credentials were provided and URL does not have credentials
        if self._username_encrypted and self._password_encrypted and "@" not in str(effective_source):
            try:
                u = decrypt_data(self._username_encrypted)
                p = decrypt_data(self._password_encrypted)
                if u and p and effective_source.startswith("rtsp://"):
                    host_part = effective_source[7:]
                    effective_source = f"rtsp://{u}:{p}@{host_part}"
            except Exception:
                pass

        super().__init__(effective_source)

    def get_public_metadata(self) -> Dict[str, Any]:
        """
        Returns strictly sanitized, public camera information for API responses and frontend dashboards.
        NEVER includes raw camera passwords or plaintext credentials.
        """
        return {
            "camera_id": self.camera_id,
            "camera_name": self.camera_name,
            "status": "ONLINE" if (self.cap is not None and self.cap.isOpened()) else "OFFLINE",
            "stream_status": "STREAMING" if (self.cap is not None and self.cap.isOpened()) else "DISCONNECTED",
            "source_masked": sanitize_rtsp_url(self.source),
            "fps": round(self.fps, 1),
            "resolution": f"{self.width}x{self.height}",
            "is_webcam": self.is_numeric,
        }

    def __repr__(self) -> str:
        return f"<CCTVStream camera_id='{self.camera_id}' name='{self.camera_name}' source='{sanitize_rtsp_url(self.source)}'>"
