"""
VirtualFit AI — Phase 8 Test Suite: Website-Native Real AI Generation.

Verifies:
1. Honest HTTP 503 Service Unavailable when genuine AI inference is requested but no worker is connected.
2. Zero customer photo storage leakage on rejected try-on requests.
3. Website-native asynchronous try-on workflow (request dispatch -> background execution -> status polling).
4. Cross-customer session isolation and privacy on try-on endpoints.
5. FashnTryOnProvider availability check and category normalization.
6. Guardrails ensuring mock provider never masquerades as genuine inference.
"""
import io
import os
import sys
import uuid
import struct
import asyncio
from pathlib import Path

# Add backend root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import HTTPException, status, UploadFile
from fastapi.background import BackgroundTasks

from app.database import SessionLocal
from app.models import User, Shop, Product, TryOnSession
from app.routers.auth import register_user
from app.routers.products import create_product
from app.routers.tryon import (
    start_tryon,
    get_tryon_status,
    get_tryon_result,
    run_tryon_background,
)
from app.schemas.auth import UserRegisterRequest
from app.schemas.product import ProductCreate
from app.services.tryon.storage import (
    CUSTOMER_PHOTOS_DIR,
    RESULTS_DIR,
    get_customer_photo_path,
    delete_customer_photo,
)
from app.services.tryon.factory import get_tryon_provider
from app.services.tryon.fashn_provider import (
    FashnTryOnProvider,
    normalize_garment_category,
)

VALID_JPEG_BYTES = (
    b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    b"\xff\xc0\x00\x11\x08\x03\x60\x02\x40\x03\x01\x11\x00\x02\x11\x01\x03\x11\x01"
    + (b"\xaa" * 500)
)


class MockUploadFile:
    def __init__(self, filename: str, content: bytes, content_type: str = "image/jpeg"):
        self.filename = filename
        self.content_type = content_type
        self.file = io.BytesIO(content)

    async def read(self, size: int = -1) -> bytes:
        return self.file.read(size)

    async def seek(self, offset: int) -> None:
        self.file.seek(offset)


class DummyBackgroundTasks:
    def __init__(self):
        self.tasks = []

    def add_task(self, func, *args, **kwargs):
        self.tasks.append((func, args, kwargs))


def setup_test_users_and_product(db):
    uid = uuid.uuid4().hex[:8]

    # Customer A
    cust_a_res = register_user(
        UserRegisterRequest(
            email=f"p8_cust_a_{uid}@example.com",
            password="CustPassword123!",
            full_name="Phase 8 Customer A",
            role="customer",
        ),
        db=db,
    )
    user_a = db.get(User, cust_a_res.user.id)

    # Customer B
    cust_b_res = register_user(
        UserRegisterRequest(
            email=f"p8_cust_b_{uid}@example.com",
            password="CustPassword123!",
            full_name="Phase 8 Customer B",
            role="customer",
        ),
        db=db,
    )
    user_b = db.get(User, cust_b_res.user.id)

    # Retailer & Shop
    ret_res = register_user(
        UserRegisterRequest(
            email=f"p8_ret_{uid}@example.com",
            password="RetPassword123!",
            full_name="Phase 8 Retailer",
            role="shop_owner",
            shop_name=f"Phase 8 Boutique {uid}",
        ),
        db=db,
    )
    ret_user = db.get(User, ret_res.user.id)
    shop = db.get(Shop, ret_user.shop_id) if ret_user.shop_id else None
    if not shop:
        shop = Shop(
            shop_name=f"Phase 8 Boutique {uid}",
            owner_name="Phase 8 Retailer",
            email=f"p8_ret_{uid}@example.com",
        )
        db.add(shop)
        db.commit()
        db.refresh(shop)
        ret_user.shop_id = shop.id
        db.commit()

    # Product with usable image
    product = create_product(
        product_in=ProductCreate(
            shop_id=shop.id,
            product_name="Heritage Silk Kurta",
            description="Pure raw silk handcrafted kurta",
            price=2499.00,
            category="Ethnic",
            image_url="/uploads/silk_kurta_p8.jpg",
            stock_quantity=15,
            is_available=True,
        ),
        current_user=ret_user,
        db=db,
    )

    return user_a, user_b, product


def test_honest_http_503_when_no_worker_connected():
    """
    Test 1: Verify that when TRYON_PROVIDER=fashn and no GPU inference worker is connected,
    start_tryon returns HTTP 503 Service Unavailable with the exact honest detail message,
    and cleanly deletes the uploaded customer photo (no storage leak).
    """
    print("\n--- Test 1: Honest HTTP 503 When No Inference Worker Is Connected ---")
    db = SessionLocal()
    user_a, _, product = setup_test_users_and_product(db)

    # Ensure no remote worker URL is set
    orig_provider = os.environ.get("TRYON_PROVIDER")
    orig_url = os.environ.get("FASHN_INFERENCE_URL")
    os.environ["TRYON_PROVIDER"] = "fashn"
    os.environ.pop("FASHN_INFERENCE_URL", None)
    os.environ.pop("REMOTE_GPU_URL", None)

    photos_before = set(CUSTOMER_PHOTOS_DIR.glob("cust_*.*"))

    upload_file = MockUploadFile("customer_photo.jpg", VALID_JPEG_BYTES)
    bg = DummyBackgroundTasks()

    try:
        try:
            asyncio.run(
                start_tryon(
                    background_tasks=bg,
                    customer_photo=upload_file,
                    product_id=product.id,
                    current_user=user_a,
                    db=db,
                )
            )
            assert False, "Expected HTTPException(503) when no inference worker is connected."
        except HTTPException as exc:
            assert exc.status_code == status.HTTP_503_SERVICE_UNAVAILABLE, (
                f"Expected HTTP 503, got {exc.status_code}"
            )
            assert exc.detail == "AI generation is temporarily unavailable because no inference worker is connected.", (
                f"Unexpected error detail: {exc.detail}"
            )
            print(f"  ✓ HTTP 503 accurately returned: '{exc.detail}'")

        # Verify no orphan customer photo remains on disk
        photos_after = set(CUSTOMER_PHOTOS_DIR.glob("cust_*.*"))
        assert photos_before == photos_after, "Customer photo was leaked on disk after HTTP 503."
        print("  ✓ Zero customer photo storage leakage verified.")

    finally:
        if orig_provider:
            os.environ["TRYON_PROVIDER"] = orig_provider
        else:
            os.environ["TRYON_PROVIDER"] = "mock"
        if orig_url:
            os.environ["FASHN_INFERENCE_URL"] = orig_url
        db.close()


def test_website_native_async_workflow():
    """
    Test 2: Verify asynchronous try-on lifecycle:
    Submission (HTTP 202) -> Task Queuing -> Status Polling -> Result Streaming.
    """
    print("\n--- Test 2: Website-Native Asynchronous Try-On Workflow ---")
    db = SessionLocal()
    user_a, _, product = setup_test_users_and_product(db)

    os.environ["TRYON_PROVIDER"] = "mock"
    upload_file = MockUploadFile("customer_portrait.jpg", VALID_JPEG_BYTES)
    bg = DummyBackgroundTasks()

    try:
        # 1. Start try-on session
        resp = asyncio.run(
            start_tryon(
                background_tasks=bg,
                customer_photo=upload_file,
                product_id=product.id,
                current_user=user_a,
                db=db,
            )
        )

        assert resp.session_id is not None
        assert resp.status == "pending"
        assert resp.progress_percentage == 0
        assert resp.is_simulation is True
        print(f"  ✓ Session initialized: ID={resp.session_id}, status={resp.status}")

        # 2. Verify background task was scheduled
        assert len(bg.tasks) >= 1
        bg_func, bg_args, bg_kwargs = bg.tasks[0]
        assert bg_func == run_tryon_background
        assert (bg_args and bg_args[0] == resp.session_id) or bg_kwargs.get("session_id") == resp.session_id
        print("  ✓ Dedicated background task scheduled via BackgroundTasks.")

        # 3. Poll status
        polled = get_tryon_status(resp.session_id, current_user=user_a, db=db)
        assert polled.session_id == resp.session_id
        assert polled.user_id == user_a.id
        assert polled.product_id == product.id
        print("  ✓ Polling endpoint GET /api/tryon/{session_id} returned accurate session metadata.")

    finally:
        db.close()


def test_cross_customer_privacy_isolation():
    """
    Test 3: Enforce strict cross-customer privacy isolation:
    - User A cannot be accessed by User B (HTTP 403).
    - Unauthenticated access is denied (HTTP 401).
    """
    print("\n--- Test 3: Cross-Customer Privacy & Isolation Enforcement ---")
    db = SessionLocal()
    user_a, user_b, product = setup_test_users_and_product(db)

    os.environ["TRYON_PROVIDER"] = "mock"
    upload_file = MockUploadFile("private_photo.jpg", VALID_JPEG_BYTES)
    bg = DummyBackgroundTasks()

    try:
        resp = asyncio.run(
            start_tryon(
                background_tasks=bg,
                customer_photo=upload_file,
                product_id=product.id,
                current_user=user_a,
                db=db,
            )
        )
        session_id = resp.session_id

        # 1. User A can access their own session
        status_a = get_tryon_status(session_id, current_user=user_a, db=db)
        assert status_a.session_id == session_id
        print("  ✓ User A successfully accessed own try-on session.")

        # 2. User B denied (HTTP 403)
        try:
            get_tryon_status(session_id, current_user=user_b, db=db)
            assert False, "Expected HTTP 403 for cross-user session access."
        except HTTPException as exc:
            assert exc.status_code == status.HTTP_403_FORBIDDEN
            print(f"  ✓ Cross-customer access blocked: HTTP 403 Forbidden.")

        # 3. Unauthenticated denied (HTTP 401)
        try:
            get_tryon_status(session_id, current_user=None, db=db)
            assert False, "Expected HTTP 401 for unauthenticated session access."
        except HTTPException as exc:
            assert exc.status_code == status.HTTP_401_UNAUTHORIZED
            print(f"  ✓ Unauthenticated access blocked: HTTP 401 Unauthorized.")

    finally:
        db.close()


def test_fashn_provider_availability_and_normalization():
    """
    Test 4: Verify FashnTryOnProvider availability logic and category normalization.
    """
    print("\n--- Test 4: Provider Availability & Category Triad Normalization ---")

    # A) Availability without worker or weights
    orig_url = os.environ.get("FASHN_INFERENCE_URL")
    os.environ.pop("FASHN_INFERENCE_URL", None)
    os.environ.pop("REMOTE_GPU_URL", None)

    fashn_p = FashnTryOnProvider(weights_dir="/nonexistent/weights")
    avail, reason = fashn_p.is_available()
    assert avail is False
    assert reason == "AI generation is temporarily unavailable because no inference worker is connected."
    print("  ✓ is_available() correctly returns False when no worker/weights are available.")

    # B) Availability with worker configured
    os.environ["FASHN_INFERENCE_URL"] = "http://127.0.0.1:8888"
    avail_with_worker, msg_with_worker = fashn_p.is_available()
    assert avail_with_worker is True
    assert "Remote inference worker" in msg_with_worker
    print(f"  ✓ is_available() correctly returns True when remote worker is configured ({msg_with_worker}).")

    if orig_url:
        os.environ["FASHN_INFERENCE_URL"] = orig_url
    else:
        os.environ.pop("FASHN_INFERENCE_URL", None)

    # C) Garment category triad normalization
    assert normalize_garment_category("Tops", "Formal Shirt") == "tops"
    assert normalize_garment_category("Ethnic", "Silk Kurta") == "tops"
    assert normalize_garment_category("Outerwear", "Leather Jacket") == "tops"
    assert normalize_garment_category("Casual", "Denim Jeans") == "bottoms"
    assert normalize_garment_category("Bottoms", "Pleated Skirt") == "bottoms"
    assert normalize_garment_category("Dresses", "Floral Maxi Dress") == "one-pieces"
    assert normalize_garment_category("One-Pieces", "Linen Jumpsuit") == "one-pieces"
    print("  ✓ Category triad normalization (tops, bottoms, one-pieces) verified.")

    # Ambiguous suit rejection
    try:
        normalize_garment_category("Suits", "Business Suit")
        assert False, "Generic business suit should be rejected as ambiguous."
    except ValueError as exc:
        print(f"  ✓ Ambiguous garment correctly rejected: {exc}")


if __name__ == "__main__":
    print("===================================================================")
    print("  RUNNING PHASE 8: WEBSITE-NATIVE REAL AI GENERATION TEST SUITE    ")
    print("===================================================================")

    test_honest_http_503_when_no_worker_connected()
    test_website_native_async_workflow()
    test_cross_customer_privacy_isolation()
    test_fashn_provider_availability_and_normalization()

    print("\n===================================================================")
    print("  ALL PHASE 8 WEBSITE-NATIVE AI GENERATION TESTS PASSED (4/4)!     ")
    print("===================================================================")
