#!/usr/bin/env python3
"""
Encryption Key Rotation Utility
===============================
Performs safe, zero-downtime key rotation for the AI Retail Intelligence Platform.

ROTATION WORKFLOW:
1. Generates a new cryptographically random Fernet key.
2. Promotes current ENCRYPTION_KEY to ENCRYPTION_KEY_OLD.
3. Sets new key as primary ENCRYPTION_KEY.
4. Verifies MultiFernet dual-key backward-compatibility.
5. Updates .env atomically.
6. Displays database migration guidance.
"""

import os
import sys
from pathlib import Path
from cryptography.fernet import Fernet, MultiFernet

def rotate_keys(env_path: Path) -> dict:
    if not env_path.exists():
        raise FileNotFoundError(f"Target .env file not found at: {env_path}")

    with open(env_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    current_primary = None
    for line in lines:
        if line.startswith("ENCRYPTION_KEY="):
            current_primary = line.strip().split("=", 1)[1]
            break

    new_primary = Fernet.generate_key().decode()

    # Validate rotation with MultiFernet
    if current_primary:
        try:
            old_f = Fernet(current_primary.encode())
            new_f = Fernet(new_primary.encode())
            multi = MultiFernet([new_f, old_f])
            
            # Test that ciphertext encrypted with old key can be decrypted and rotated
            sample_ct = old_f.encrypt(b"rotation_validation_token")
            decrypted = multi.decrypt(sample_ct)
            rotated_ct = multi.rotate(sample_ct)
            re_decrypted = new_f.decrypt(rotated_ct)

            if decrypted != b"rotation_validation_token" or re_decrypted != b"rotation_validation_token":
                raise ValueError("Verification check failed during key rotation simulation.")
        except Exception as e:
            raise RuntimeError(f"Cryptographic pre-rotation check failed: {e}")

    # Build updated .env content
    new_lines = []
    has_primary = False
    has_old = False

    for line in lines:
        if line.startswith("ENCRYPTION_KEY="):
            new_lines.append(f"ENCRYPTION_KEY={new_primary}\n")
            has_primary = True
        elif line.startswith("ENCRYPTION_KEY_OLD="):
            new_lines.append(f"ENCRYPTION_KEY_OLD={current_primary or ''}\n")
            has_old = True
        else:
            new_lines.append(line)

    if not has_primary:
        new_lines.append(f"ENCRYPTION_KEY={new_primary}\n")
    if not has_old:
        new_lines.append(f"ENCRYPTION_KEY_OLD={current_primary or ''}\n")

    # Atomic write to .env
    temp_path = env_path.with_suffix(".tmp")
    with open(temp_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)
    temp_path.replace(env_path)

    return {
        "success": True,
        "old_key_masked": (current_primary[:4] + "...." + current_primary[-4:]) if current_primary else "NONE",
        "new_key_masked": new_primary[:4] + "...." + new_primary[-4:],
        "message": "Key rotation completed successfully. .env updated with ENCRYPTION_KEY and ENCRYPTION_KEY_OLD."
    }


if __name__ == "__main__":
    base_dir = Path(__file__).resolve().parent.parent
    env_file = base_dir / ".env"

    print("==================================================")
    print("🔐 AI RETAIL PLATFORM - KEY ROTATION UTILITY")
    print("==================================================")

    try:
        res = rotate_keys(env_file)
        print(" [OK] Key Rotation Successful!")
        print(f" - Previous Key (Archived to OLD): {res['old_key_masked']}")
        print(f" - New Primary Key (Active):      {res['new_key_masked']}")
        print("\nNote: MultiFernet will decrypt data using both keys seamlessly.")
        print("Run database re-encryption when ready to fully retire the old key.")
    except Exception as err:
        print(f"❌ [ERROR] Key rotation failed: {err}", file=sys.stderr)
        sys.exit(1)
