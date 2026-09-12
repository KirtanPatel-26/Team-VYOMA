"""
Central Encryption Service
==========================
Production-grade authenticated encryption layer for AI Retail Intelligence Platform.
Uses Cryptography Fernet (AES-128-CBC + HMAC-SHA256 authenticated encryption).
Supports seamless key rotation via MultiFernet (ENCRYPTION_KEY_CURRENT and ENCRYPTION_KEY_OLD).

SECURITY PRINCIPLES:
1. Never log plaintext secrets or encryption keys.
2. Never expose keys to client frontend or API responses.
3. Fail safely if key is missing or corrupted.
4. Consistent UTF-8 encoding.
"""

import os
import json
import logging
from pathlib import Path
from typing import Any, Optional, Union
from cryptography.fernet import Fernet, MultiFernet, InvalidToken

try:
    from dotenv import load_dotenv
    # Search current directory and up to 3 parent levels for .env
    current = Path(__file__).resolve().parent
    for _ in range(4):
        candidate = current / ".env"
        if candidate.exists():
            load_dotenv(candidate)
            break
        current = current.parent
except ImportError:
    pass

logger = logging.getLogger("security.encryption")


class SecurityError(Exception):
    """Base exception for security operations."""
    pass


class EncryptionKeyMissingError(SecurityError):
    """Raised when the encryption key is missing or blank in the environment."""
    pass


class EncryptionKeyInvalidError(SecurityError):
    """Raised when the encryption key is improperly formatted."""
    pass


class DecryptionError(SecurityError):
    """Raised when ciphertext cannot be authenticated or decrypted."""
    pass


class EncryptionService:
    """
    Centralized authenticated encryption service.
    Implements AES-128-CBC + HMAC-SHA256 via Fernet / MultiFernet.
    """

    def __init__(
        self,
        primary_key: Optional[str] = None,
        secondary_key: Optional[str] = None
    ):
        self._primary_key = primary_key
        self._secondary_key = secondary_key
        self._cipher: Optional[MultiFernet] = None
        self._primary_fernet: Optional[Fernet] = None
        self._is_initialized = False

        self._initialize()

    def _initialize(self) -> None:
        """Validates and instantiates Fernet cryptographic engines."""
        key_str = self._primary_key if self._primary_key is not None else os.getenv("ENCRYPTION_KEY", "")
        old_key_str = self._secondary_key if self._secondary_key is not None else os.getenv("ENCRYPTION_KEY_OLD", "")

        if not key_str or not key_str.strip():
            # Will raise on encryption/decryption calls if still unconfigured
            self._is_initialized = False
            return

        key_bytes = key_str.strip().encode("utf-8")
        try:
            self._primary_fernet = Fernet(key_bytes)
            fernets = [self._primary_fernet]
        except Exception as e:
            raise EncryptionKeyInvalidError(
                "Primary ENCRYPTION_KEY is invalid. Expected 32 url-safe base64-encoded bytes."
            ) from None

        if old_key_str and old_key_str.strip():
            try:
                old_bytes = old_key_str.strip().encode("utf-8")
                fernets.append(Fernet(old_bytes))
            except Exception:
                logger.warning("[Security] Warning: ENCRYPTION_KEY_OLD is malformed; continuing with primary key only.")

        self._cipher = MultiFernet(fernets)
        self._is_initialized = True

    def ensure_initialized(self) -> None:
        """Verifies encryption engine is operational, attempting re-init from env if needed."""
        if not self._is_initialized or self._cipher is None:
            if self._primary_key is None:
                self._initialize()
            if not self._is_initialized or self._cipher is None:
                raise EncryptionKeyMissingError(
                    "ENCRYPTION_KEY is not configured in the environment. "
                    "Generate a key using Fernet.generate_key() and set ENCRYPTION_KEY in .env."
                )

    def is_configured(self) -> bool:
        """Checks if valid encryption keys are loaded."""
        try:
            self.ensure_initialized()
            return True
        except SecurityError:
            return False

    def encrypt_data(self, data: Union[str, bytes, dict, list, int, float, None]) -> Optional[str]:
        """
        Encrypts arbitrary data using authenticated AES-Fernet.
        Strings and numbers are encoded to UTF-8; dicts/lists are converted to JSON.
        Returns URL-safe base64 ciphertext string, or None if data is None.
        """
        if data is None:
            return None

        self.ensure_initialized()

        try:
            if isinstance(data, (dict, list)):
                raw_str = json.dumps(data, separators=(",", ":"))
                raw_bytes = raw_str.encode("utf-8")
            elif isinstance(data, str):
                raw_bytes = data.encode("utf-8")
            elif isinstance(data, (int, float, bool)):
                raw_bytes = str(data).encode("utf-8")
            elif isinstance(data, (bytes, bytearray)):
                raw_bytes = bytes(data)
            else:
                raw_bytes = str(data).encode("utf-8")

            # MultiFernet.encrypt always uses the primary key
            ciphertext_bytes = self._cipher.encrypt(raw_bytes)
            return ciphertext_bytes.decode("utf-8")
        except Exception as e:
            if isinstance(e, SecurityError):
                raise
            logger.error("[Security] Encryption failed safely without exposing plaintext.")
            raise SecurityError("Failed to encrypt sensitive data.") from None

    def decrypt_data(self, ciphertext: Optional[str]) -> Optional[str]:
        """
        Decrypts Fernet ciphertext to a UTF-8 string.
        Supports automatic rotation fallback if ciphertext was encrypted with ENCRYPTION_KEY_OLD.
        Returns None if ciphertext is None or empty.
        """
        if ciphertext is None or ciphertext == "":
            return None

        self.ensure_initialized()

        try:
            ct_bytes = str(ciphertext).strip().encode("utf-8")
            decrypted_bytes = self._cipher.decrypt(ct_bytes)
            return decrypted_bytes.decode("utf-8")
        except InvalidToken:
            logger.error("[Security] Decryption authentication failed: invalid token or wrong key.")
            raise DecryptionError("Decryption failed: corrupted ciphertext or authentication mismatch.") from None
        except Exception as e:
            if isinstance(e, SecurityError):
                raise
            logger.error("[Security] Decryption failed safely.")
            raise DecryptionError("Decryption error occurred.") from None

    def decrypt_json(self, ciphertext: Optional[str]) -> Any:
        """
        Decrypts ciphertext and deserializes the JSON payload.
        Returns None if ciphertext is None.
        """
        plaintext = self.decrypt_data(ciphertext)
        if plaintext is None:
            return None
        try:
            return json.loads(plaintext)
        except Exception:
            # If not JSON, return the raw string
            return plaintext

    def rotate_ciphertext(self, ciphertext: str) -> str:
        """
        Re-encrypts ciphertext with the primary key if it was encrypted with an older key.
        """
        if not ciphertext:
            return ciphertext
        self.ensure_initialized()
        try:
            ct_bytes = ciphertext.strip().encode("utf-8")
            rotated_bytes = self._cipher.rotate(ct_bytes)
            return rotated_bytes.decode("utf-8")
        except Exception as e:
            logger.error("[Security] Ciphertext rotation failed.")
            raise SecurityError("Failed to rotate ciphertext to current primary key.") from None

    @staticmethod
    def is_encrypted(value: Any) -> bool:
        """
        Heuristic check for Fernet token:
        Fernet tokens are URL-safe base64 strings starting with 'gAAAAA'.
        """
        if not isinstance(value, str):
            return False
        stripped = value.strip()
        # Fernet format begins with version 0x80 -> base64 'gAAAAA'
        return stripped.startswith("gAAAAA") and len(stripped) >= 100


# Global singleton encryption service
encryption_service = EncryptionService()


def encrypt_data(data: Union[str, bytes, dict, list, int, float, None]) -> Optional[str]:
    """Convenience module function for encrypting data."""
    return encryption_service.encrypt_data(data)


def decrypt_data(ciphertext: Optional[str]) -> Optional[str]:
    """Convenience module function for decrypting data."""
    return encryption_service.decrypt_data(ciphertext)


def decrypt_json(ciphertext: Optional[str]) -> Any:
    """Convenience module function for decrypting JSON data."""
    return encryption_service.decrypt_json(ciphertext)


is_encrypted = EncryptionService.is_encrypted
