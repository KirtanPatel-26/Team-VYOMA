"""
Security Sanitizer & Masking Utility
====================================
Prevents leakage of sensitive credentials, passwords, encryption keys,
and PII across API responses, logs, and user interfaces.
"""

import re
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlparse, urlunparse

# Common sensitive dictionary keys that must be redacted or sanitized
SENSITIVE_FIELD_NAMES = {
    "password", "camera_password", "rtsp_password", "pass",
    "secret", "jwt_secret", "encryption_key", "encryption_key_old",
    "supabase_service_role_key", "service_role_key", "api_key",
    "gemini_api_key", "token", "access_token", "private_key"
}


def sanitize_rtsp_url(url: Union[str, int, None], mask_user: bool = False) -> str:
    """
    Sanitizes RTSP, HTTP, or RTMP camera URLs by masking user credentials.
    
    Examples:
        rtsp://admin:superSecret123@192.168.1.50:554/h264 -> rtsp://admin:******@192.168.1.50:554/h264
        rtsp://admin:pass@cam.local/live (mask_user=True) -> rtsp://******:******@cam.local/live
        0 -> "0"
        "videos/store.mp4" -> "videos/store.mp4"
    """
    if url is None:
        return ""
    if isinstance(url, int):
        return str(url)

    url_str = str(url).strip()
    if not url_str:
        return ""

    # Check if URL contains credentials pattern
    # Regex handles protocols like rtsp://, rtmp://, http://, https://
    pattern = re.compile(r'^(rtsp|rtmp|http|https)://([^@]+)@(.*)$', re.IGNORECASE)
    match = pattern.match(url_str)
    if not match:
        return url_str

    proto, creds, rest = match.groups()
    if ":" in creds:
        username, _ = creds.split(":", 1)
        user_display = "******" if mask_user else username
        return f"{proto}://{user_display}:******@{rest}"
    else:
        return f"{proto}://******@{rest}"


def extract_rtsp_credentials(rtsp_url: str) -> tuple[Optional[str], Optional[str], str]:
    """
    Extracts (username, password, clean_base_url) from an RTSP string.
    Returns:
        (username, password, "rtsp://hostname:port/stream")
    """
    if not rtsp_url or not isinstance(rtsp_url, str):
        return None, None, str(rtsp_url or "")

    pattern = re.compile(r'^(rtsp|rtmp|http|https)://(?:([^:]+):([^@]+)@)?(.*)$', re.IGNORECASE)
    match = pattern.match(rtsp_url.strip())
    if not match:
        return None, None, rtsp_url

    proto, user, password, host_and_path = match.groups()
    clean_url = f"{proto}://{host_and_path}"
    return user, password, clean_url


def mask_credential(val: Optional[str], visible_chars: int = 4) -> str:
    """
    Masks sensitive string values, showing only leading/trailing characters.
    """
    if not val:
        return ""
    val_str = str(val).strip()
    length = len(val_str)
    if length <= 4:
        return "****"
    if length <= 8:
        return val_str[:2] + "****" + val_str[-1:]
    half = min(visible_chars, length // 4)
    return val_str[:half] + "..." + val_str[-half:]


def mask_email(email: Optional[str]) -> str:
    """
    Masks an email address for safe display while retaining domain context.
    Example: shopper_test@example.com -> sh***st@example.com
    """
    if not email or "@" not in email:
        return mask_credential(email)
    local, domain = email.strip().split("@", 1)
    if len(local) <= 2:
        masked_local = local[0] + "*" if local else "*"
    else:
        masked_local = local[:2] + "*" * (len(local) - 3) + local[-1]
    return f"{masked_local}@{domain}"


def mask_phone(phone: Optional[str]) -> str:
    """
    Masks a phone number, preserving the last 4 digits.
    Example: +919876543210 -> +91******3210
    """
    if not phone:
        return ""
    cleaned = str(phone).strip()
    if len(cleaned) <= 4:
        return "****"
    return cleaned[:-4] + "****" if len(cleaned) < 8 else cleaned[:3] + "*" * (len(cleaned) - 7) + cleaned[-4:]


def sanitize_dict(
    payload: Any,
    redact_keys: Optional[set] = None
) -> Any:
    """
    Recursively scrubs sensitive keys from dictionary payloads before serialization.
    """
    keys_to_redact = (redact_keys or SENSITIVE_FIELD_NAMES)

    if isinstance(payload, dict):
        sanitized = {}
        for k, v in payload.items():
            k_lower = str(k).lower()
            if any(secret in k_lower for secret in keys_to_redact):
                sanitized[k] = "[REDACTED]"
            elif "rtsp" in k_lower or "camera_url" in k_lower or "stream_url" in k_lower:
                sanitized[k] = sanitize_rtsp_url(v)
            else:
                sanitized[k] = sanitize_dict(v, keys_to_redact)
        return sanitized
    elif isinstance(payload, list):
        return [sanitize_dict(item, keys_to_redact) for item in payload]
    elif isinstance(payload, str):
        # Quick RTSP pattern check inside strings
        if payload.startswith("rtsp://") or payload.startswith("rtmp://"):
            return sanitize_rtsp_url(payload)
        return payload
    return payload
