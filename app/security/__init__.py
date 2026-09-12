"""
Security Package
================
Centralized encryption, sanitization, and authorization services.
"""

from app.security.encryption import (
    EncryptionService,
    encryption_service,
    encrypt_data,
    decrypt_data,
    decrypt_json,
    SecurityError,
    EncryptionKeyMissingError,
    EncryptionKeyInvalidError,
    DecryptionError,
)
from app.security.sanitizer import (
    sanitize_rtsp_url,
    extract_rtsp_credentials,
    mask_credential,
    mask_email,
    mask_phone,
    sanitize_dict,
)
from app.security.auth import (
    create_access_token,
    verify_jwt_token,
    get_current_user,
    require_role,
)

__all__ = [
    "EncryptionService",
    "encryption_service",
    "encrypt_data",
    "decrypt_data",
    "decrypt_json",
    "SecurityError",
    "EncryptionKeyMissingError",
    "EncryptionKeyInvalidError",
    "DecryptionError",
    "sanitize_rtsp_url",
    "extract_rtsp_credentials",
    "mask_credential",
    "mask_email",
    "mask_phone",
    "sanitize_dict",
    "create_access_token",
    "verify_jwt_token",
    "get_current_user",
    "require_role",
]
