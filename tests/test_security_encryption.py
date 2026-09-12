"""
Security & Encryption Test Suite
================================
Validates cryptographic integrity, key rotation, RTSP credential protection,
API response sanitization, and STORE_001 preservation vs STORE_002 encryption.
"""

import pytest
from fastapi.testclient import TestClient
from cryptography.fernet import Fernet

from app.security.encryption import (
    EncryptionService,
    encrypt_data,
    decrypt_data,
    decrypt_json,
    DecryptionError,
    EncryptionKeyMissingError,
    is_encrypted,
)
from app.security.sanitizer import (
    sanitize_rtsp_url,
    mask_credential,
    mask_email,
    mask_phone,
    extract_rtsp_credentials,
)
from app.camera.cctv import CCTVStream
from app.main import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# 1. CORE ENCRYPTION & DECRYPTION TESTS
# ---------------------------------------------------------------------------

def test_fernet_encryption_roundtrip():
    """Verify authentic encryption-decryption round trip."""
    original = "shopper_sensitive_pii@retailstore.com"
    ciphertext = encrypt_data(original)
    assert ciphertext is not None
    assert ciphertext != original
    assert ciphertext.startswith("gAAAAA")
    assert is_encrypted(ciphertext)

    decrypted = decrypt_data(ciphertext)
    assert decrypted == original


def test_encryption_data_types():
    """Verify handling of JSON dicts, lists, integers, and Unicode strings."""
    # Unicode / Hindi text
    hindi_text = "स्मार्ट रिटेल इंटेलिजेंस"
    assert decrypt_data(encrypt_data(hindi_text)) == hindi_text

    # Complex dictionary
    payload = {"shopper_id": 42, "loyalty_tier": "Gold", "cart": ["SKU001", "SKU002"]}
    enc_payload = encrypt_data(payload)
    assert is_encrypted(enc_payload)
    decrypted_obj = decrypt_json(enc_payload)
    assert decrypted_obj == payload

    # None handling
    assert encrypt_data(None) is None
    assert decrypt_data(None) is None


def test_invalid_ciphertext_handling():
    """Corrupted or invalid ciphertext must fail safely without leaking details."""
    with pytest.raises(DecryptionError):
        decrypt_data("gAAAAABcorruptedTokenInvalidCiphertextPaddingError12345678901234567890")


def test_wrong_key_fails_decryption():
    """Ciphertext encrypted with Key A cannot be decrypted with Key B."""
    key_a = Fernet.generate_key().decode()
    key_b = Fernet.generate_key().decode()

    service_a = EncryptionService(primary_key=key_a)
    service_b = EncryptionService(primary_key=key_b)

    ct = service_a.encrypt_data("confidential_secret")
    with pytest.raises(DecryptionError):
        service_b.decrypt_data(ct)


def test_missing_key_fails_safely():
    """Service fails safely with a clear configuration error if key is empty."""
    service_empty = EncryptionService(primary_key="")
    with pytest.raises(EncryptionKeyMissingError):
        service_empty.encrypt_data("some_text")


# ---------------------------------------------------------------------------
# 2. DUAL-KEY ROTATION TESTS
# ---------------------------------------------------------------------------

def test_dual_key_rotation_flow():
    """
    Test zero-downtime key rotation:
    Data encrypted with OLD key can be decrypted and rotated to NEW primary key.
    """
    old_key = Fernet.generate_key().decode()
    new_key = Fernet.generate_key().decode()

    # Step 1: Encrypt data using old key
    old_service = EncryptionService(primary_key=old_key)
    ciphertext_old = old_service.encrypt_data("card_token_987654")

    # Step 2: Initialize service with new primary and old secondary key
    dual_service = EncryptionService(primary_key=new_key, secondary_key=old_key)

    # Must successfully decrypt using secondary key fallback
    decrypted = dual_service.decrypt_data(ciphertext_old)
    assert decrypted == "card_token_987654"

    # Step 3: Rotate ciphertext to new primary key
    rotated_ct = dual_service.rotate_ciphertext(ciphertext_old)
    assert rotated_ct != ciphertext_old

    # Step 4: Standalone new service with only new key can now decrypt
    new_only_service = EncryptionService(primary_key=new_key)
    assert new_only_service.decrypt_data(rotated_ct) == "card_token_987654"


# ---------------------------------------------------------------------------
# 3. RTSP & PII SANITIZATION TESTS
# ---------------------------------------------------------------------------

def test_rtsp_url_sanitization():
    """Verify camera passwords and usernames are masked in RTSP streams."""
    raw_rtsp = "rtsp://admin:VerySecurePassword123@192.168.1.100:554/h264/ch1/main"
    sanitized = sanitize_rtsp_url(raw_rtsp)
    assert "VerySecurePassword123" not in sanitized
    assert sanitized == "rtsp://admin:******@192.168.1.100:554/h264/ch1/main"

    # Fully masked username
    fully_masked = sanitize_rtsp_url(raw_rtsp, mask_user=True)
    assert "admin" not in fully_masked
    assert fully_masked == "rtsp://******:******@192.168.1.100:554/h264/ch1/main"

    # Non-credential sources remain untouched
    assert sanitize_rtsp_url("0") == "0"
    assert sanitize_rtsp_url(0) == "0"
    assert sanitize_rtsp_url("videos/store.mp4") == "videos/store.mp4"


def test_extract_rtsp_credentials():
    """Safely splits RTSP URL into user, password, and clean stream endpoint."""
    user, pwd, clean_url = extract_rtsp_credentials("rtsp://guard_user:cctv_pass@10.0.0.5:554/live")
    assert user == "guard_user"
    assert pwd == "cctv_pass"
    assert clean_url == "rtsp://10.0.0.5:554/live"


def test_pii_masking_helpers():
    """Test customer email and phone masking."""
    # customer.retail (15 chars) -> "cu" + 12 stars + "l"
    assert mask_email("customer.retail@gmail.com") == "cu************l@gmail.com"
    # +919876543210 (13 chars) -> "+91" + 6 stars + "3210"
    assert mask_phone("+919876543210") == "+91******3210"
    assert mask_credential("SuperSecretAPIKey") == "Supe...IKey"


# ---------------------------------------------------------------------------
# 4. CCTV CLASS CREDENTIAL SECURITY
# ---------------------------------------------------------------------------

def test_cctv_stream_credential_protection():
    """CCTVStream object must never expose password in representation or metadata."""
    cctv = CCTVStream(
        source="videos/store.mp4",
        camera_id="CAM_CHECKOUT_02",
        camera_name="Checkout Counter Camera 2"
    )
    meta = cctv.get_public_metadata()
    assert meta["camera_id"] == "CAM_CHECKOUT_02"
    assert "password" not in meta
    assert "raw_source" not in meta
    assert "password" not in repr(cctv).lower()


# ---------------------------------------------------------------------------
# 5. API SECURITY & STORE_001 VS STORE_002 ENCRYPTION ISOLATION
# ---------------------------------------------------------------------------

def test_api_security_health_endpoint():
    """Verify security health endpoint confirms encryption without leaking key."""
    res = client.get("/api/security/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "HEALTHY"
    assert data["encryption_layer"]["key_configured"] is True
    assert data["encryption_layer"]["operational_verification"] is True
    # Strictly ensure key itself is NEVER present in response
    assert "ENCRYPTION_KEY" not in str(data)
    assert "bNVTn3Lx" not in str(data)


def test_api_camera_devices_does_not_leak_credentials():
    """Verify camera endpoints sanitize active sources."""
    res = client.get("/api/camera/devices")
    assert res.status_code == 200
    data = res.json()
    assert "active_source" in data
    # Must not contain '@' with password
    assert "@" not in data["active_source"] or "******" in data["active_source"]


def test_store_001_preservation_vs_store_002_encryption():
    """
    CRITICAL REQUIREMENT:
    STORE_001 must remain completely standard and unencrypted.
    STORE_002 must apply application-level encryption for customer PII & cashier data.
    """
    items = [{"sku_id": "SKU001", "quantity": 1}]

    # Test STORE_001: Standard unencrypted receipt
    res_s1 = client.post("/api/billing/sale", json={
        "items": items,
        "payment_method": "UPI",
        "cashier": "Cashier Indiranagar",
        "store_code": "STORE_001",
        "customer_email": "shopper1@gmail.com"
    })
    assert res_s1.status_code == 200
    data_s1 = res_s1.json()
    assert data_s1["success"] is True
    assert data_s1["store_id"] == "STORE_001"
    assert data_s1["security_mode"] == "STANDARD"
    # STORE_001 does not encrypt customer_email
    assert "customer_email_encrypted" not in data_s1

    # Test STORE_002: Encrypted receipt with masked PII
    res_s2 = client.post("/api/billing/sale", json={
        "items": items,
        "payment_method": "UPI",
        "cashier": "Cashier Bandra",
        "store_code": "STORE_002",
        "customer_email": "shopper2@gmail.com",
        "customer_phone": "+919876543210"
    })
    assert res_s2.status_code == 200
    data_s2 = res_s2.json()
    assert data_s2["success"] is True
    assert data_s2["store_id"] == "STORE_002"
    assert data_s2["security_mode"] == "APPLICATION_ENCRYPTED"
    assert "customer_email_encrypted" in data_s2
    assert is_encrypted(data_s2["customer_email_encrypted"])
    assert "customer_phone_encrypted" in data_s2
    assert is_encrypted(data_s2["customer_phone_encrypted"])
    assert data_s2["customer_email_masked"] == "sh*****2@gmail.com"
    assert "shopper2@gmail.com" not in data_s2["customer_email_masked"]

    # Decrypt verification through Central Encryption Service
    decrypted_email = decrypt_data(data_s2["customer_email_encrypted"])
    assert decrypted_email == "shopper2@gmail.com"
