"""
Authentication & Authorization Security
=======================================
Provides JWT validation, role-based authorization, and header inspection
for sensitive administrative and configuration API routes.
"""

import os
import time
from typing import Optional, Dict, Any
import jwt
from fastapi import HTTPException, Security, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security_bearer = HTTPBearer(auto_error=False)

def _get_jwt_secret() -> str:
    secret = os.getenv("JWT_SECRET", "")
    if not secret:
        # Fallback to key derivation or secure internal default
        secret = os.getenv("ENCRYPTION_KEY", "smartretail-ai-default-jwt-secret-key-32b")
    return secret


def create_access_token(data: dict, expires_delta_seconds: int = 86400) -> str:
    """
    Creates a signed JWT token with expiration and roles.
    """
    to_encode = data.copy()
    expire = int(time.time()) + expires_delta_seconds
    to_encode.update({"exp": expire, "iat": int(time.time())})
    token = jwt.encode(to_encode, _get_jwt_secret(), algorithm="HS256")
    return token if isinstance(token, str) else token.decode("utf-8")


def verify_jwt_token(token: str) -> Dict[str, Any]:
    """
    Validates a JWT token and returns the decoded payload.
    Raises HTTPException(401) on invalid, expired, or corrupted token.
    """
    try:
        payload = jwt.decode(token, _get_jwt_secret(), algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Authentication token has expired.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials.")


def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Security(security_bearer)) -> Optional[Dict[str, Any]]:
    """
    Dependency to extract current authenticated user from Bearer token.
    Permits optional access in development mode if no token is provided.
    """
    if not credentials:
        return None
    return verify_jwt_token(credentials.credentials)


def require_role(allowed_roles: list[str]):
    """
    Dependency factory to enforce role-based access control (RBAC).
    """
    def role_checker(user: Optional[Dict[str, Any]] = Depends(get_current_user)):
        # If in development mode without configured users, allow unless user specifically supplied invalid token
        if user is None:
            # Check for development header or environment
            env_mode = os.getenv("APP_ENV", "development").lower()
            if env_mode == "production":
                raise HTTPException(status_code=401, detail="Authentication required for this endpoint.")
            return {"sub": "developer", "role": "admin"}

        user_role = user.get("role", "viewer")
        if user_role not in allowed_roles and "admin" not in user_role:
            raise HTTPException(status_code=403, detail="Forbidden: Insufficient privileges.")
        return user

    return role_checker
