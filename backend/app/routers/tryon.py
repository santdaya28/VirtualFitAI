"""
Virtual Try-On Router for VirtualFit AI.

Endpoints:
- POST /api/tryon: Accepts customer photo upload and product_id, initializes session,
  and dispatches asynchronous background try-on processing (HTTP 202 Accepted).
- GET /api/tryon/{session_id}: Polls current progress, stage messages, and completion state.
- GET /api/tryon/{session_id}/result: Streams the genuine AI-generated try-on result image.

Security & Privacy:
- Customer photos are stored exclusively in private temporary storage; never in public static directories.
- Internal storage paths and customer photos are never exposed to API responses.
- Path traversal protection enforced on all storage access.
- Simulation output explicitly states that no genuine AI fitting image was produced.
- Concurrency ceiling enforced via asyncio.Semaphore to protect CPU/GPU memory.
"""
import os
import uuid
import logging
import asyncio
import struct
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    UploadFile,
    File,
    Form,
    Query,
    BackgroundTasks,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.database import get_db, SessionLocal
from app.models import Product, Shop, TryOnSession, User
from app.schemas.tryon import (
    TryOnStatusResponse,
    TryOnInputsResponse,
    TryOnHistoryItemResponse,
)
from app.services.tryon.storage import (
    save_customer_photo,
    delete_customer_photo,
    cleanup_expired_files,
    get_result_path,
    get_customer_photo_path,
    delete_result_file,
    RESULTS_DIR,
)
from app.services.tryon.factory import get_tryon_provider
from app.services.tryon import normalize_garment_category
from app.services.tryon.zerogpu_provider import (
    classify_upstream_error,
    sanitize_public_error_message,
)
from app.core.security import get_optional_user, get_current_user

logger = logging.getLogger("virtualfit.tryon.router")

router = APIRouter(prefix="/api/tryon", tags=["Virtual Try-On"])

# 10 MB maximum allowed upload size
MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024

# Concurrency semaphore for neural network inferences
_inference_semaphore: Optional[asyncio.Semaphore] = None


def get_inference_semaphore() -> asyncio.Semaphore:
    """
    Returns the singleton concurrency semaphore limiting parallel neural network inferences.
    Prevents parallel GPU VRAM / CPU RAM exhaustion across concurrent background tasks.
    Configured via environment variable FASHN_MAX_CONCURRENT_INFERENCES (default: 1).
    """
    global _inference_semaphore
    if _inference_semaphore is None:
        try:
            limit = int(os.getenv("FASHN_MAX_CONCURRENT_INFERENCES", "1"))
        except (ValueError, TypeError):
            limit = 1
        _inference_semaphore = asyncio.Semaphore(max(1, limit))
    return _inference_semaphore


def get_db_session(db: Optional[Session] = Depends(get_db)) -> Session:
    """
    Dependency ensuring active database session is available.
    Returns HTTP 503 if PostgreSQL is unreachable.
    """
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection is not available. Please verify PostgreSQL service is running.",
        )
    return db


def verify_session_access(session: TryOnSession, current_user: Optional[User]) -> None:
    """
    Enforces customer privacy and data isolation:
    - If the session was created by an authenticated user (user_id is not None):
        - Unauthenticated access is denied (HTTP 401).
        - Access by a different user is denied (HTTP 403) unless user is admin.
    - If the session was created anonymously (user_id is None):
        - Access is allowed by session UUID token.
    """
    user = current_user if isinstance(current_user, User) else None
    if session.user_id is not None:
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required to access this private try-on session.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if user.role != "admin" and user.id != session.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You do not have permission to view or modify this session.",
            )



def validate_image_file(contents: bytes, filename: Optional[str] = None) -> str:
    """
    Validates uploaded file contents using magic byte headers.
    Ensures file is genuine JPEG, PNG, or WebP.
    Returns normalized extension (e.g. '.jpg', '.png', '.webp').
    Raises HTTPException(400) if invalid or unsupported.
    """
    if len(contents) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded customer photo is empty.",
        )

    if len(contents) > MAX_UPLOAD_SIZE_BYTES:
        size_mb = len(contents) / (1024 * 1024)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Customer photo size ({size_mb:.2f} MB) exceeds the maximum allowed limit of 10 MB.",
        )

    if len(contents) < 12:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is too small to be a valid image.",
        )

    # Magic byte verification
    # JPEG check: FF D8 FF
    if contents.startswith(b"\xff\xd8\xff"):
        return ".jpg"

    # PNG check: 89 50 4E 47 0D 0A 1A 0A
    if contents.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"

    # WebP check: RIFF....WEBP
    if contents.startswith(b"RIFF") and contents[8:12] == b"WEBP":
        return ".webp"

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Unsupported or invalid image format. Allowed formats: JPEG, PNG, WebP.",
    )


def parse_image_dimensions(contents: bytes, ext: str) -> Optional[tuple[int, int]]:
    """
    Parses image dimensions (width, height) directly from raw byte headers
    without requiring third-party imaging dependencies (e.g. PIL).
    Returns (width, height) tuple or None if dimensions cannot be determined.
    """
    try:
        # PNG format
        if ext == ".png" and contents.startswith(b"\x89PNG\r\n\x1a\n"):
            if len(contents) >= 24:
                w, h = struct.unpack(">II", contents[16:24])
                return (w, h)

        # JPEG format
        elif ext == ".jpg" or contents.startswith(b"\xff\xd8\xff"):
            idx = 2
            length = len(contents)
            while idx < length - 9:
                if contents[idx] != 0xFF:
                    idx += 1
                    continue
                marker = contents[idx + 1]
                # SOF0 (0xC0), SOF1 (0xC1), SOF2 (0xC2), SOF3 (0xC3)
                if marker in (0xC0, 0xC1, 0xC2, 0xC3):
                    h, w = struct.unpack(">HH", contents[idx + 5 : idx + 9])
                    return (w, h)
                # Skip marker segment: 2 bytes length (includes length bytes themselves)
                if idx + 4 > length:
                    break
                seg_len = struct.unpack(">H", contents[idx + 2 : idx + 4])[0]
                idx += 2 + seg_len

        # WebP format
        elif ext == ".webp" and contents.startswith(b"RIFF") and contents[8:12] == b"WEBP":
            chunk_type = contents[12:16]
            if chunk_type == b"VP8 " and len(contents) >= 30:
                w, h = struct.unpack("<HH", contents[26:30])
                return (w & 0x3FFF, h & 0x3FFF)
            elif chunk_type == b"VP8L" and len(contents) >= 25:
                b0, b1, b2, b3 = contents[21:25]
                w = 1 + (((b1 & 0x3F) << 8) | b0)
                h = 1 + (((b3 & 0x0F) << 10) | (b2 << 2) | ((b1 & 0xC0) >> 6))
                return (w, h)
            elif chunk_type == b"VP8X" and len(contents) >= 30:
                w = 1 + struct.unpack("<I", contents[24:27] + b"\x00")[0]
                h = 1 + struct.unpack("<I", contents[27:30] + b"\x00")[0]
                return (w, h)
    except Exception as exc:
        logger.debug(f"Could not parse image dimensions from header: {exc}")
    return None



async def run_tryon_background(
    session_id: str,
    customer_photo_filename: str,
    product_image_url: str,
    category: Optional[str] = None,
) -> None:
    """
    Dedicated background worker executing Virtual Try-On processing asynchronously.
    Enforces concurrency ceiling via get_inference_semaphore() to protect CPU/GPU resources.
    Opens and closes an isolated SQLAlchemy session to ensure request lifecycle separation.
    Safely captures exceptions to record genuine failure states in PostgreSQL.
    """
    logger.info(f"[BackgroundTask] Queuing virtual try-on processing for session: {session_id}")

    bg_db: Optional[Session] = None
    if SessionLocal is not None:
        try:
            bg_db = SessionLocal()
        except Exception as exc:
            logger.error(f"[BackgroundTask] Failed to create dedicated DB session: {exc}")

    semaphore = get_inference_semaphore()
    async with semaphore:
        try:
            provider = get_tryon_provider()
            logger.info(
                f"[BackgroundTask] Commencing try-on execution with provider '{provider.provider_name}' "
                f"for session: {session_id}"
            )
            exec_result = await provider.process_tryon(
                session_id=session_id,
                customer_photo_path=customer_photo_filename,
                garment_image_url=product_image_url,
                category=category,
                db=bg_db,
            )
            if exec_result.status == "failed":
                logger.warning(
                    f"[BackgroundTask] Virtual try-on failed for session '{session_id}' "
                    f"[category={exec_result.error_category or 'unknown'}]: {exec_result.error_message}"
                )
            else:
                logger.info(f"[BackgroundTask] Successfully completed virtual try-on for session: {session_id}")

        except Exception as exc:
            logger.error(
                f"[BackgroundTask] Unexpected error in session '{session_id}': {exc}",
                exc_info=True,
            )
            if bg_db is not None:
                try:
                    session = bg_db.get(TryOnSession, session_id)
                    if session:
                        classified = classify_upstream_error(exc=exc)
                        safe_err = sanitize_public_error_message(classified.public_message)
                        session.status = "failed"
                        session.stage_message = f"AI generation failed: {safe_err}"[:250]
                        session.error_message = safe_err
                        session.error_category = classified.category
                        session.retry_after_seconds = classified.retry_after_seconds
                        session.quota_resets_at = classified.quota_resets_at
                        session.updated_at = datetime.now(timezone.utc)
                        bg_db.commit()
                except Exception as db_exc:
                    logger.error(f"[BackgroundTask] Failed to mark session as failed in DB: {db_exc}")
                    try:
                        bg_db.rollback()
                    except Exception:
                        pass
        finally:
            if bg_db is not None:
                try:
                    bg_db.close()
                except Exception:
                    pass


def _resolve_product_shop_context(
    db: Session,
    product: Optional[Product],
) -> tuple[Optional[int], Optional[str], Optional[str]]:
    """Return (shop_id, shop_slug, shop_name) for a product when available."""
    if product is None or product.shop_id is None:
        return (None, None, None)
    shop = product.shop or db.get(Shop, product.shop_id)
    if shop is None:
        return (product.shop_id, None, None)
    return (shop.id, shop.slug, shop.shop_name)


@router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=TryOnStatusResponse,
    summary="Start Virtual Try-On",
    description=(
        "Submits customer photo and selected retail product_id to initialize "
        "an asynchronous virtual clothing try-on session."
    ),
)
async def start_tryon(
    background_tasks: BackgroundTasks,
    customer_photo: UploadFile = File(..., description="Customer photo image file (JPEG, PNG, WebP, max 10 MB)"),
    product_id: int = Form(..., ge=1, description="Integer ID of the retail product to try on"),
    shop_id: Optional[int] = Form(default=None, ge=1, description="Optional storefront shop ID to validate product membership"),
    shop_slug: Optional[str] = Form(default=None, description="Optional storefront slug to validate product membership"),
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db_session),
):
    """
    Initializes a new Virtual Try-On session.
    1. Validates image size and magic byte signature.
    2. Verifies that product exists, is published, and belongs to the requested shop storefront.
    3. Saves customer photo to private temporary storage.
    4. Resolves configured try-on provider dynamically.
    5. Records TryOnSession in PostgreSQL (associating user_id if authenticated).
    6. Dispatches background processing and returns HTTP 202 Accepted immediately.
    """
    # 1. Read and validate customer photo binary content
    try:
        contents = await customer_photo.read()
    except Exception as exc:
        logger.error(f"Error reading uploaded customer photo: {exc}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to read uploaded photo file.",
        )

    detected_ext = validate_image_file(contents, customer_photo.filename)

    # 2. Verify that selected product exists and enforce shop isolation
    user = current_user if isinstance(current_user, User) else None
    req_shop_id = shop_id if isinstance(shop_id, int) else None
    req_shop_slug = shop_slug.strip().lower() if isinstance(shop_slug, str) and shop_slug.strip() else None

    expected_shop: Optional[Shop] = None
    if req_shop_slug is not None:
        expected_shop = db.scalar(select(Shop).where(func.lower(Shop.slug) == req_shop_slug))
        if not expected_shop:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Storefront '{req_shop_slug}' not found.",
            )
        if req_shop_id is not None and expected_shop.id != req_shop_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Conflicting storefront shop_id and shop_slug parameters.",
            )
    elif req_shop_id is not None:
        expected_shop = db.get(Shop, req_shop_id)
        if not expected_shop:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Shop with ID {req_shop_id} not found.",
            )

    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID {product_id} not found.",
        )

    if expected_shop is not None and product.shop_id != expected_shop.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Cross-shop violation: Product ID {product_id} does not belong to storefront "
                f"'{expected_shop.shop_name}'."
            ),
        )

    if expected_shop is None and user is not None and user.role == "shop_owner":
        if user.shop_id is None or product.shop_id != user.shop_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Cross-shop violation: Product ID {product_id} does not belong to your shop.",
            )

    is_owning_shop_user = bool(
        user is not None
        and (
            user.role == "admin"
            or (user.role == "shop_owner" and user.shop_id == product.shop_id)
        )
    )
    if not product.is_available and not is_owning_shop_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Product '{product.product_name}' is not currently published for virtual try-on.",
        )

    # 3. Verify product has a usable image
    if not product.image_url or not product.image_url.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Product '{product.product_name}' (ID: {product_id}) does not have a usable image for virtual try-on.",
        )

    # 3b. Prevent accidental duplicate concurrent generation for the same customer + garment
    if user is not None:
        existing_active = db.scalars(
            select(TryOnSession)
            .where(
                TryOnSession.user_id == user.id,
                TryOnSession.product_id == product.id,
                TryOnSession.status.in_(["pending", "processing"]),
            )
            .order_by(TryOnSession.created_at.desc())
            .limit(1)
        ).first()
        if existing_active is not None:
            ts = existing_active.updated_at or existing_active.created_at
            is_recent = True
            if ts is not None:
                now_cmp = datetime.now(timezone.utc) if ts.tzinfo else datetime.utcnow()
                is_recent = (now_cmp - ts).total_seconds() < 300
            if is_recent:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="An AI try-on generation for this garment is already in progress. Please wait for it to finish.",
                )

    # 4. Save customer photo to private temporary storage
    try:
        internal_photo_name = save_customer_photo(
            contents,
            original_filename=customer_photo.filename,
            extension=detected_ext,
        )
    except Exception as exc:
        logger.error(f"Failed to store customer photo in private storage: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to securely store customer photo.",
        )

    # 5. Resolve configured try-on provider dynamically
    try:
        active_provider = get_tryon_provider()
        active_provider_name = active_provider.provider_name
    except Exception as exc:
        logger.error(f"Failed to resolve configured try-on provider: {exc}")
        delete_customer_photo(internal_photo_name)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Try-on provider configuration error. Please try again later.",
        )

    # 5b. Worker availability verification for AI inference providers (e.g. FASHN VTON)
    if hasattr(active_provider, "is_available"):
        is_avail, avail_msg = active_provider.is_available()
        if not is_avail:
            delete_customer_photo(internal_photo_name)
            logger.warning(
                f"Try-on generation unavailable for provider '{active_provider_name}': {avail_msg}"
            )
            safe_avail_msg = sanitize_public_error_message(avail_msg) if avail_msg else ""
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=safe_avail_msg or "AI generation is temporarily unavailable because no inference worker is connected.",
            )

    # 6. Create TryOnSession record in PostgreSQL
    session_id = str(uuid.uuid4())
    is_simulation = (active_provider_name == "mock")
    if active_provider_name == "zerogpu":
        provenance = "genuine_zerogpu"
    elif active_provider_name == "fashn":
        provenance = "genuine_inference"
    else:
        provenance = "mock_simulation"
    user_id = user.id if user else None

    if is_simulation:
        init_stage_message = "Try-on simulation queued successfully. No AI fitting image has been generated."
    else:
        init_stage_message = f"Virtual try-on queued successfully for {active_provider_name.upper()} processing."

    new_session = TryOnSession(
        id=session_id,
        customer_photo_url=internal_photo_name,
        product_id=product.id,
        garment_id=None,
        user_id=user_id,
        status="pending",
        progress_percentage=0,
        stage_message=init_stage_message,
        provider=active_provider_name,
        provenance=provenance,
        result_image_url=None,
        error_message=None,
    )

    try:
        db.add(new_session)
        db.commit()
        db.refresh(new_session)
    except Exception as exc:
        db.rollback()
        # Clean up stored photo if DB insert fails
        delete_customer_photo(internal_photo_name)
        logger.error(f"Database error saving TryOnSession: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error while initializing virtual try-on session.",
        )

    try:
        resolved_category = normalize_garment_category(
            category=product.category,
            product_name=product.product_name,
        )
    except ValueError:
        resolved_category = product.category

    # 7. Schedule asynchronous background processing
    background_tasks.add_task(
        run_tryon_background,
        session_id=session_id,
        customer_photo_filename=internal_photo_name,
        product_image_url=product.image_url,
        category=resolved_category,
    )

    # 8. Opportunistically clean expired temporary files (> 1 hour) in background
    background_tasks.add_task(cleanup_expired_files, 3600)

    logger.info(
        f"Queued try-on session '{session_id}' for product ID {product.id} "
        f"using provider '{active_provider_name}' (user_id: {user_id})"
    )

    resolved_shop_id, resolved_shop_slug, resolved_shop_name = _resolve_product_shop_context(db, product)
    return TryOnStatusResponse(
        session_id=session_id,
        product_id=product.id,
        shop_id=resolved_shop_id,
        shop_slug=resolved_shop_slug,
        shop_name=resolved_shop_name,
        garment_id=None,
        user_id=user_id,
        status="pending",
        provider=active_provider_name,
        provenance=provenance,
        progress_percentage=0,
        stage_message=init_stage_message,
        message=init_stage_message,
        result_image_url=None,
        error_message=None,
        is_simulation=is_simulation,
        created_at=new_session.created_at,
        updated_at=new_session.updated_at,
    )


@router.get(
    "/history/me",
    response_model=List[TryOnHistoryItemResponse],
    summary="Get customer try-on history",
    description="Retrieves a list of all virtual try-on sessions created by the authenticated user.",
)
def get_user_tryon_history(
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db_session),
):
    """
    Returns personal try-on history for the authenticated customer.
    Enforces customer privacy isolation: users cannot see other customers' sessions.
    """
    num_limit = limit if isinstance(limit, int) else 50
    stmt = (
        select(TryOnSession)
        .where(TryOnSession.user_id == current_user.id)
        .order_by(TryOnSession.created_at.desc())
        .limit(num_limit)
    )
    sessions = db.scalars(stmt).all()

    items = []
    for s in sessions:
        prod = s.product
        s_shop_id, s_shop_slug, s_shop_name = _resolve_product_shop_context(db, prod)
        items.append(
            TryOnHistoryItemResponse(
                session_id=s.id,
                product_id=s.product_id,
                product_name=prod.product_name if prod else None,
                shop_id=s_shop_id,
                shop_slug=s_shop_slug,
                shop_name=s_shop_name,
                category=prod.category if prod else None,
                garment_image_url=prod.image_url if prod else None,
                status=s.status,
                progress_percentage=s.progress_percentage,
                stage_message=s.stage_message,
                provider=s.provider,
                provenance=s.provenance or (
                    "mock_simulation" if s.provider == "mock"
                    else "genuine_zerogpu" if s.provider == "zerogpu"
                    else "manual_import"
                ),
                result_image_url=s.result_image_url,
                created_at=s.created_at,
                updated_at=s.updated_at,
            )
        )
    return items


@router.get(
    "/{session_id}",
    response_model=TryOnStatusResponse,
    summary="Check Try-On Status",
    description="Polls progress and current status of an ongoing or completed virtual try-on task.",
)
def get_tryon_status(
    session_id: str,
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db_session),
):
    """
    Retrieves status for a virtual try-on task by session ID.
    Enforces customer session data isolation.
    Returns HTTP 404 if session is not found.
    """
    session = db.get(TryOnSession, session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Virtual Try-On session '{session_id}' not found.",
        )

    verify_session_access(session, current_user)

    # For completed mock sessions, clearly state that no AI fitting image was produced
    stage_msg = session.stage_message
    safe_err_msg = sanitize_public_error_message(session.error_message) if session.error_message else None
    if session.status == "completed" and session.provider == "mock":
        stage_msg = "Simulation completed. No AI-generated fitting image was produced."
    elif session.status == "failed":
        if not stage_msg:
            stage_msg = safe_err_msg or "Virtual try-on processing failed."
        else:
            stage_msg = sanitize_public_error_message(stage_msg)

    s_shop_id, s_shop_slug, s_shop_name = _resolve_product_shop_context(db, session.product)
    return TryOnStatusResponse(
        session_id=session.id,
        product_id=session.product_id,
        shop_id=s_shop_id,
        shop_slug=s_shop_slug,
        shop_name=s_shop_name,
        garment_id=session.garment_id,
        user_id=session.user_id,
        status=session.status,
        provider=session.provider,
        provenance=session.provenance or (
            "mock_simulation" if session.provider == "mock"
            else "genuine_zerogpu" if session.provider == "zerogpu"
            else "manual_import"
        ),
        progress_percentage=session.progress_percentage,
        stage_message=stage_msg,
        message=stage_msg,
        result_image_url=session.result_image_url,
        error_message=safe_err_msg,
        error_category=getattr(session, "error_category", None),
        retry_after_seconds=getattr(session, "retry_after_seconds", None),
        quota_resets_at=getattr(session, "quota_resets_at", None),
        is_simulation=(session.provider == "mock"),
        created_at=session.created_at,
        updated_at=session.updated_at,
    )



@router.get(
    "/{session_id}/result",
    summary="Get Try-On Result Image",
    description="Streams the genuine AI-generated try-on result image for a completed session.",
)
def get_tryon_result(
    session_id: str,
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db_session),
):
    """
    Retrieves and streams the generated virtual try-on image for a completed session.
    Enforces customer privacy isolation.
    """
    session = db.get(TryOnSession, session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Virtual Try-On session '{session_id}' not found.",
        )

    verify_session_access(session, current_user)


    # 1. State validation
    if session.status in ("pending", "processing"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Virtual try-on generation for session '{session_id}' is still in progress "
                f"(status: '{session.status}', progress: {session.progress_percentage}%)."
            ),
        )

    if session.status == "failed":
        safe_detail = sanitize_public_error_message(
            session.error_message or session.stage_message or "Internal processing failure."
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Virtual try-on generation for session '{session_id}' failed: {safe_detail}",
        )

    if session.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Virtual try-on session '{session_id}' is not in completed state (status: '{session.status}').",
        )

    # 2. Check result URL
    if not session.result_image_url:
        detail_msg = f"No result image is available for session '{session_id}'."
        if session.provider == "mock":
            detail_msg += " (Mock simulation does not generate AI fitting images.)"
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail_msg,
        )

    # 3. Resolve result file path safely
    candidate_filenames = [
        f"res_{session_id}.jpg",
        f"res_{session_id}.png",
        f"res_{session_id}.webp",
    ]
    url_base = os.path.basename(session.result_image_url.strip())
    if url_base and url_base != "result" and url_base not in candidate_filenames:
        candidate_filenames.insert(0, url_base)

    resolved_file_path: Optional[Path] = None
    for fname in candidate_filenames:
        try:
            target = get_result_path(fname)
            if target.exists() and target.is_file():
                resolved_file_path = target
                break
        except (ValueError, FileNotFoundError):
            continue

    if resolved_file_path is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Result image for session '{session_id}' was not found in storage or has expired.",
        )

    ext = resolved_file_path.suffix.lower()
    media_type = "image/jpeg"
    if ext == ".png":
        media_type = "image/png"
    elif ext == ".webp":
        media_type = "image/webp"

    return FileResponse(
        path=str(resolved_file_path),
        media_type=media_type,
        filename=f"tryon_{session_id}{ext}",
        headers={
            "Cache-Control": "private, max-age=3600",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get(
    "/{session_id}/inputs",
    response_model=TryOnInputsResponse,
    summary="Get Try-On Session Inputs for Colab",
    description="Exports session inputs metadata and download paths for manual Colab inference.",
)
def get_tryon_inputs(
    session_id: str,
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db_session),
):
    """
    Retrieves input metadata for a virtual try-on session.
    Enforces customer data isolation.
    """
    session = db.get(TryOnSession, session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Virtual Try-On session '{session_id}' not found.",
        )

    verify_session_access(session, current_user)

    product = db.get(Product, session.product_id) if session.product_id else None
    cat_raw = product.category if product else None
    prod_name = product.product_name if product else "Unknown Product"
    normalized_category = normalize_garment_category(cat_raw, prod_name)

    return TryOnInputsResponse(
        session_id=session.id,
        product_id=session.product_id or 0,
        product_name=prod_name,
        category=normalized_category,
        customer_photo_download_url=f"/api/tryon/{session.id}/customer-photo",
        garment_image_url=product.image_url if product and product.image_url else "",
        created_at=session.created_at,
    )


@router.get(
    "/{session_id}/customer-photo",
    summary="Download Customer Photo for Session",
    description="Streams the private customer photo for manual Colab inference workflow in development.",
)
def get_customer_photo_for_session(
    session_id: str,
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db_session),
):
    """
    Streams the private customer photo for an active session to allow manual export to Colab.
    Enforces customer privacy isolation and path traversal protection.
    """
    session = db.get(TryOnSession, session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Virtual Try-On session '{session_id}' not found.",
        )

    verify_session_access(session, current_user)

    if not session.customer_photo_url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No customer photo recorded for session '{session_id}'.",
        )

    try:
        photo_path = get_customer_photo_path(session.customer_photo_url)
    except (ValueError, FileNotFoundError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer photo for session '{session_id}' was not found in storage or has expired.",
        )

    ext = photo_path.suffix.lower()
    media_type = "image/jpeg"
    if ext == ".png":
        media_type = "image/png"
    elif ext == ".webp":
        media_type = "image/webp"

    return FileResponse(
        path=str(photo_path),
        media_type=media_type,
        filename=f"customer_photo_{session_id}{ext}",
        headers={
            "Cache-Control": "private, max-age=3600",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post(
    "/{session_id}/import-result",
    response_model=TryOnStatusResponse,
    summary="Import FASHN VTON Result",
    description=(
        "Manual AI workflow endpoint for development and testing. "
        "Imports a result image produced by FASHN VTON in Colab into the active session."
    ),
)
async def import_tryon_result(
    session_id: str,
    result_image: UploadFile = File(..., description="FASHN VTON result image file (JPEG, PNG, WebP)"),
    allow_overwrite: bool = Query(False, description="Set to true to explicitly permit re-importing over an existing result"),
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db_session),
):
    """
    Imports an AI virtual try-on result generated manually in Colab.
    1. Validates session existence in PostgreSQL and caller access permissions.
    2. Protects against duplicate import / accidental overwriting.
    3. Validates image payload magic bytes and maximum size (<= 10 MB).
    4. Validates image dimensions (between 100x100 and 4096x4096).
    5. Securely persists the result image to RESULTS_DIR.
    6. Updates session record with honest provenance='manual_import' and provider='fashn_manual'.
    """
    session = db.get(TryOnSession, session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Virtual Try-On session '{session_id}' not found.",
        )

    verify_session_access(session, current_user)

    # Duplicate import protection
    should_overwrite = allow_overwrite if isinstance(allow_overwrite, bool) else False
    if session.status == "completed" and session.result_image_url and not should_overwrite:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Session already has an imported result image. Set allow_overwrite=true to re-import.",
        )

    # 1. Read binary content
    try:
        contents = await result_image.read()
    except Exception as exc:
        logger.error(f"Error reading uploaded result image: {exc}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to read uploaded result image file.",
        )

    # 2. Magic byte and size verification
    detected_ext = validate_image_file(contents, result_image.filename)

    # 3. Dimension bounds validation
    dims = parse_image_dimensions(contents, detected_ext)
    if dims is not None:
        w, h = dims
        if w < 100 or h < 100 or w > 4096 or h > 4096:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Image dimensions ({w}x{h}) outside allowed range (100x100 to 4096x4096).",
            )

    # 4. Target destination inside RESULTS_DIR with traversal protection
    target_filename = f"res_{session_id}{detected_ext}"
    try:
        target_path = (RESULTS_DIR / target_filename).resolve()
        if target_path.parent != RESULTS_DIR.resolve():
            raise ValueError("Path traversal detected.")
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid storage path: {exc}",
        )

    try:
        with open(target_path, "wb") as f:
            f.write(contents)
    except Exception as exc:
        logger.error(f"Failed to write imported result image for session {session_id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to persist imported result image to storage.",
        )

    # 5. Update database session record with honest provenance
    session.status = "completed"
    session.progress_percentage = 100
    session.stage_message = "AI Fitting Complete (try-on result imported)."
    session.provider = "fashn_manual"
    session.provenance = "manual_import"
    session.result_image_url = f"/api/tryon/{session_id}/result"
    session.error_message = None
    session.updated_at = datetime.now(timezone.utc)

    try:
        db.commit()
        db.refresh(session)
    except Exception as exc:
        db.rollback()
        logger.error(f"Database error updating session {session_id} after result import: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error updating try-on session with imported result.",
        )

    logger.info(f"Successfully imported result for session '{session_id}' (provenance: manual_import).")

    s_shop_id, s_shop_slug, s_shop_name = _resolve_product_shop_context(db, session.product)
    return TryOnStatusResponse(
        session_id=session.id,
        product_id=session.product_id,
        shop_id=s_shop_id,
        shop_slug=s_shop_slug,
        shop_name=s_shop_name,
        garment_id=session.garment_id,
        user_id=session.user_id,
        status="completed",
        provider="fashn_manual",
        provenance="manual_import",
        progress_percentage=100,
        stage_message=session.stage_message,
        message=session.stage_message,
        result_image_url=session.result_image_url,
        error_message=None,
        is_simulation=False,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


@router.delete(
    "/{session_id}",
    summary="Delete try-on session and private images",
    description="Permanently deletes customer photo, generated result, and database record on demand for user privacy.",
)
def delete_tryon_session(
    session_id: str,
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db_session),
):
    """
    On-demand data deletion honoring customer privacy.
    Purges customer photo, result images, and database record.
    """
    session = db.get(TryOnSession, session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Virtual Try-On session '{session_id}' not found.",
        )

    verify_session_access(session, current_user)

    # 1. Delete customer photo
    if session.customer_photo_url:
        delete_customer_photo(session.customer_photo_url)

    # 2. Delete result image if exists
    for ext in (".jpg", ".png", ".webp"):
        delete_result_file(f"res_{session_id}{ext}")

    # 3. Delete database record
    try:
        db.delete(session)
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error(f"Failed to delete session {session_id} from database: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error while deleting try-on session.",
        )

    return {
        "status": "success",
        "message": f"Try-on session '{session_id}' and all associated private image assets permanently purged.",
        "session_id": session_id,
    }


