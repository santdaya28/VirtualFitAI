"""
Core Security & Authentication Module for VirtualFit AI.

Features:
- Cryptographically secure password hashing using PBKDF2-HMAC-SHA256 (100,000 iterations, 16-byte random salt).
- Constant-time password verification using hmac.compare_digest to prevent timing attacks.
- Cryptographically signed bearer tokens with HMAC-SHA256 and expiration timestamps.
- Zero external dependencies: utilizes standard library hashlib, hmac, secrets, and base64.
- FastAPI dependencies for current_user, optional_user, and role-based access control (RBAC).
"""
import os
import json
import hmac
import time
import base64
import hashlib
import secrets
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone, timedelta

from fastapi import Depends, HTTPException, Header, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database import get_db
from app.models import User, RevokedToken

logger = logging.getLogger("virtualfit.security")

# Application Secret Key for token signing
SECRET_KEY = os.getenv("SECRET_KEY", "virtualfit_ai_production_grade_secret_key_2026_super_secure")
TOKEN_EXPIRATION_SECONDS = 7 * 24 * 3600  # 7 days


# =============================================================================
# PASSWORD HASHING (PBKDF2-HMAC-SHA256)
# =============================================================================

def hash_password(password: str) -> str:
    """
    Hashes a password using PBKDF2-HMAC-SHA256 with 100,000 rounds and a random salt.
    Format: 'pbkdf2:sha256:100000$<salt_hex>$<hash_hex>'
    """
    if not password:
        raise ValueError("Password cannot be empty.")
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
    return f"pbkdf2:sha256:100000${salt.hex()}${dk.hex()}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifies a plain password against the stored PBKDF2 hash using constant-time comparison.
    """
    if not plain_password or not hashed_password:
        return False
    try:
        parts = hashed_password.split("$")
        if len(parts) != 3:
            return False
        header, salt_hex, expected_hash_hex = parts
        algorithm, sub_algo, iterations = header.split(":")
        if algorithm != "pbkdf2" or sub_algo != "sha256":
            return False
        salt = bytes.fromhex(salt_hex)
        dk = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt, int(iterations))
        return hmac.compare_digest(dk.hex(), expected_hash_hex)
    except Exception as exc:
        logger.error(f"Error during password verification: {exc}")
        return False


# =============================================================================
# CRYPTOGRAPHICALLY SIGNED BEARER TOKENS
# =============================================================================

def create_access_token(
    user_id: int,
    email: str,
    role: str,
    shop_id: Optional[int] = None,
    expires_in: int = TOKEN_EXPIRATION_SECONDS,
) -> str:
    """
    Creates a cryptographically signed URL-safe bearer token.
    Token structure: base64url(payload).base64url(hmac_signature)
    """
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "shop_id": shop_id,
        "exp": int(time.time()) + expires_in,
        "iat": int(time.time()),
    }
    payload_json = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    payload_b64 = base64.urlsafe_b64encode(payload_json).decode("ascii").rstrip("=")

    signature = hmac.new(
        SECRET_KEY.encode("utf-8"),
        payload_b64.encode("ascii"),
        hashlib.sha256,
    ).digest()
    sig_b64 = base64.urlsafe_b64encode(signature).decode("ascii").rstrip("=")

    return f"{payload_b64}.{sig_b64}"


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Validates token signature and expiration.
    Returns decoded payload dict if valid, or None if invalid or expired.
    """
    if not token or "." not in token:
        return None
    try:
        parts = token.split(".")
        if len(parts) != 2:
            return None
        payload_b64, sig_b64 = parts

        # Verify signature in constant time
        expected_sig = hmac.new(
            SECRET_KEY.encode("utf-8"),
            payload_b64.encode("ascii"),
            hashlib.sha256,
        ).digest()
        expected_sig_b64 = base64.urlsafe_b64encode(expected_sig).decode("ascii").rstrip("=")

        if not hmac.compare_digest(sig_b64, expected_sig_b64):
            return None

        # Decode payload
        padding = "=" * (-len(payload_b64) % 4)
        payload_json = base64.urlsafe_b64decode(payload_b64 + padding).decode("utf-8")
        payload = json.loads(payload_json)

        # Check expiration
        exp = payload.get("exp")
        if not exp or time.time() > exp:
            return None

        return payload
    except Exception as exc:
        logger.debug(f"Failed to decode token: {exc}")
        return None


def hash_token(token: str) -> str:
    """
    Computes SHA-256 digest of token string for constant-length database indexing.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def is_token_revoked(token: str, db: Optional[Session]) -> bool:
    """
    Checks if a bearer token has been explicitly revoked via logout.
    """
    if not token or db is None:
        return False
    try:
        token_digest = hash_token(token)
        revoked = db.scalar(select(RevokedToken).where(RevokedToken.token_hash == token_digest))
        return revoked is not None
    except Exception as exc:
        logger.error(f"Error checking token revocation status: {exc}")
        return False


def revoke_token(token: str, db: Session, expires_at: Optional[datetime] = None) -> bool:
    """
    Revokes a bearer token server-side upon user logout.
    Stores the token hash until expiration, and cleans up old expired revocation records.
    """
    if not token or db is None:
        return False
    try:
        payload = decode_access_token(token)
        token_digest = hash_token(token)

        exp_dt = expires_at
        if not exp_dt:
            if payload and "exp" in payload:
                exp_dt = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
            else:
                exp_dt = datetime.now(timezone.utc) + timedelta(days=7)

        existing = db.scalar(select(RevokedToken).where(RevokedToken.token_hash == token_digest))
        if not existing:
            new_revoked = RevokedToken(
                token_hash=token_digest,
                expires_at=exp_dt,
            )
            db.add(new_revoked)
            # Opportunistic cleanup of expired revocation records
            now = datetime.now(timezone.utc)
            db.query(RevokedToken).filter(RevokedToken.expires_at < now).delete(synchronize_session=False)
            db.commit()
            logger.info(f"Revoked token hash '{token_digest[:8]}...' until {exp_dt}")
        return True
    except Exception as exc:
        db.rollback()
        logger.error(f"Failed to record token revocation: {exc}")
        return False


# =============================================================================
# FASTAPI DEPENDENCIES FOR AUTHENTICATION & RBAC
# =============================================================================

def get_optional_user(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    db: Optional[Session] = Depends(get_db),
) -> Optional[User]:
    """
    Extracts and verifies Bearer token if provided.
    Returns active User entity if valid token is supplied, or None if anonymous.
    Rejects revoked tokens (e.g. after logout).
    """
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization[7:].strip()

    # Check token revocation
    if db is not None and is_token_revoked(token, db):
        logger.info("Bearer token rejected: Token has been revoked.")
        return None

    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        return None

    if db is None:
        return None

    user = db.get(User, payload["sub"])
    if not user or not user.is_active:
        return None
    return user


def get_current_user(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    db: Optional[Session] = Depends(get_db),
) -> User:
    """
    Requires an active, authenticated User.
    Raises HTTP 401 Unauthorized if missing, invalid, or expired.
    """
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:].strip()
        if db is not None and is_token_revoked(token, db):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked. Please sign in again.",
                headers={"WWW-Authenticate": "Bearer"},
            )
    user = get_optional_user(authorization=authorization, db=db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please provide a valid Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_role(allowed_roles: List[str]):
    """
    Dependency factory enforcing role-based access control.
    """
    def _role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required role in {allowed_roles}, but your role is '{current_user.role}'.",
            )
        return current_user
    return _role_checker


require_customer = require_role(["customer", "admin"])
require_shop_owner = require_role(["shop_owner", "admin"])

