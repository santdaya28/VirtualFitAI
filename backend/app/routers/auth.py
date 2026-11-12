"""
Authentication Router for VirtualFit AI.

Endpoints:
- POST /api/auth/register: Registers new customer or shop owner accounts with rate limiting.
- POST /api/auth/login: Authenticates credentials and returns signed access token with rate limiting.
- GET /api/auth/me: Retrieves profile of current authenticated user.
- DELETE /api/auth/me: Permanently deletes user account, private try-on assets, and shops (Right to Erasure).
- POST /api/auth/logout: Revokes active bearer token server-side.
"""
import os
import logging
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Header, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database import get_db
from app.models import User, Shop, Product, TryOnSession
from app.core.slugs import generate_unique_shop_slug
from app.schemas.auth import (
    UserRegisterRequest,
    UserLoginRequest,
    UserResponse,
    AuthTokenResponse,
)
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
    revoke_token,
)
from app.core.rate_limiter import RateLimiter
from app.services.tryon.storage import (
    delete_customer_photo,
    delete_result_file,
)

logger = logging.getLogger("virtualfit.auth")

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

# Rate limiters for brute-force protection
login_limiter = RateLimiter(
    max_requests=int(os.getenv("RATE_LIMIT_LOGIN_MAX_CALLS", "5")),
    window_seconds=int(os.getenv("RATE_LIMIT_LOGIN_WINDOW_SECONDS", "60")),
    scope="login",
)
register_limiter = RateLimiter(
    max_requests=int(os.getenv("RATE_LIMIT_REGISTER_MAX_CALLS", "3")),
    window_seconds=int(os.getenv("RATE_LIMIT_REGISTER_WINDOW_SECONDS", "60")),
    scope="register",
)


def get_db_session(db: Optional[Session] = Depends(get_db)) -> Session:
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection is not available.",
        )
    return db


@router.post(
    "/register",
    response_model=AuthTokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description="Registers a new customer or shop owner account. Shop owners are automatically provisioned a boutique shop.",
    dependencies=[Depends(register_limiter)],
)
def register_user(
    req: UserRegisterRequest,
    db: Session = Depends(get_db_session),
):
    clean_email = req.email.strip().lower()

    # 1. Verify email uniqueness
    existing_user = db.scalar(select(User).where(User.email == clean_email))
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"An account with email '{clean_email}' already exists.",
        )

    # 2. If registering as shop_owner, create or resolve shop
    shop_id: Optional[int] = None
    if req.role == "shop_owner":
        shop_title = req.shop_name.strip() if req.shop_name else f"{req.full_name or 'Retailer'}'s Boutique"
        new_shop = Shop(
            shop_name=shop_title,
            slug=generate_unique_shop_slug(db, shop_title),
            owner_name=req.full_name,
            email=clean_email,
        )
        db.add(new_shop)
        db.flush()
        shop_id = new_shop.id

    # 3. Create user record
    new_user = User(
        email=clean_email,
        hashed_password=hash_password(req.password),
        full_name=req.full_name.strip() if req.full_name else None,
        role=req.role,
        shop_id=shop_id,
        is_active=True,
    )
    db.add(new_user)
    try:
        db.commit()
        db.refresh(new_user)
    except Exception as exc:
        db.rollback()
        logger.error(f"Error registering user: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error occurred during user registration.",
        )

    # 4. Generate bearer token
    token = create_access_token(
        user_id=new_user.id,
        email=new_user.email,
        role=new_user.role,
        shop_id=new_user.shop_id,
    )
    logger.info(f"Registered new user ID {new_user.id} ({new_user.email}) as role='{new_user.role}'")

    return AuthTokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse.model_validate(new_user),
    )


@router.post(
    "/login",
    response_model=AuthTokenResponse,
    summary="Login user",
    description="Authenticates credentials and returns a signed bearer token.",
    dependencies=[Depends(login_limiter)],
)
def login_user(
    req: UserLoginRequest,
    db: Session = Depends(get_db_session),
):
    clean_email = req.email.strip().lower()
    user = db.scalar(select(User).where(User.email == clean_email))

    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been deactivated. Please contact support.",
        )

    token = create_access_token(
        user_id=user.id,
        email=user.email,
        role=user.role,
        shop_id=user.shop_id,
    )
    logger.info(f"User {user.id} ({user.email}) authenticated successfully.")

    return AuthTokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
    )


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user profile",
    description="Retrieves profile information for the active authenticated user.",
)
def get_me(
    current_user: User = Depends(get_current_user),
):
    return UserResponse.model_validate(current_user)


@router.delete(
    "/me",
    status_code=status.HTTP_200_OK,
    summary="Delete user account and cascade personal data",
    description=(
        "Permanently deletes user account, all associated private try-on sessions, "
        "customer photos, result images, and owned shop products under GDPR / DPDP right to erasure."
    ),
)
def delete_account(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    user_id = current_user.id
    email = current_user.email
    role = current_user.role

    # 1. Cascade cleanup of TryOnSessions and private image files
    user_sessions = db.scalars(
        select(TryOnSession).where(TryOnSession.user_id == user_id)
    ).all()
    sessions_count = len(user_sessions)
    for sess in user_sessions:
        if sess.customer_photo_url:
            delete_customer_photo(sess.customer_photo_url)
        for ext in (".jpg", ".png", ".webp"):
            delete_result_file(f"res_{sess.id}{ext}")
        db.delete(sess)

    # 2. If user is a shop_owner, cascade cleanup of owned shop and products
    if current_user.shop_id:
        shop = db.get(Shop, current_user.shop_id)
        if shop:
            for prod in shop.products:
                if prod.image_url and prod.image_url.startswith("/uploads/"):
                    img_filename = os.path.basename(prod.image_url)
                    img_path = (Path(__file__).resolve().parent.parent.parent / "uploads" / img_filename).resolve()
                    if img_path.exists() and img_path.is_file():
                        try:
                            img_path.unlink()
                        except Exception as e:
                            logger.warning(f"Could not delete product image {img_path}: {e}")
            db.delete(shop)

    # 3. Revoke bearer token if present
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:].strip()
        revoke_token(token, db)

    # 4. Delete user record
    db.delete(current_user)

    try:
        db.commit()
        logger.info(f"Permanently deleted account user_id={user_id} ({role}), {sessions_count} tryon sessions purged.")
    except Exception as exc:
        db.rollback()
        logger.error(f"Failed to delete user account {user_id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error while deleting account and personal data.",
        )

    return {
        "status": "success",
        "message": "Account, personal data, and associated try-on assets permanently deleted.",
        "user_id": user_id,
        "purged_sessions_count": sessions_count,
    }


@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    summary="Log out and invalidate token",
    description="Revokes the active bearer token server-side so it cannot be reused.",
)
def logout_user(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:].strip()
        revoke_token(token, db)
        logger.info(f"User {current_user.id} ({current_user.email}) logged out; token revoked.")
    return {
        "status": "success",
        "message": "Successfully logged out and revoked bearer token.",
    }

