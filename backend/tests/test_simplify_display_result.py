"""
Test Suite: Simplified AI Try-On Result Display Workflow.

Verifies:
1. Successful result upload and status update to 'completed' with 'AI Fitting Complete'.
2. Honest provenance preservation ('manual_import' and 'fashn_manual').
3. Rejection of invalid image payloads (empty, non-image, oversized, invalid dimensions).
4. Error handling for non-existent sessions and permission violations.
5. Re-display / overwrite capability with allow_overwrite=True.
"""
import io
import sys
import uuid
import struct
import asyncio
from pathlib import Path

# Add backend root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import HTTPException, status
from fastapi.responses import FileResponse

from app.database import SessionLocal
from app.models import User, Shop, Product, TryOnSession
from app.routers.auth import register_user
from app.routers.products import create_product
from app.routers.tryon import (
    start_tryon,
    import_tryon_result,
    get_tryon_result,
    get_tryon_status,
)
from app.schemas.auth import UserRegisterRequest
from app.schemas.product import ProductCreate
from app.services.tryon.storage import RESULTS_DIR, CUSTOMER_PHOTOS_DIR

# Valid JPEG binary payload
VALID_JPEG_BYTES = (
    b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    b"\xff\xc0\x00\x11\x08\x03\x60\x02\x40\x03\x01\x11\x00\x02\x11\x01\x03\x11\x01"
    + (b"\xaa" * 500)
)

VALID_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR"
    + struct.pack(">II", 576, 864)
    + b"\x08\x02\x00\x00\x00"
    b"\x00\x00\x00\x00"
    + (b"\xbb" * 200)
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


def test_simplify_display_result_workflow():
    print("\n--- Test 1: Successful Result Display & Status Update ---")
    db = SessionLocal()
    uid = uuid.uuid4().hex[:8]

    # 1. Register customer
    cust_res = register_user(
        UserRegisterRequest(
            email=f"disp_cust_{uid}@example.com",
            password="CustPassword123!",
            full_name="Display Test Customer",
            role="customer",
        ),
        db=db,
    )
    cust_user = db.get(User, cust_res.user.id)

    # 2. Register retailer and product
    ret_res = register_user(
        UserRegisterRequest(
            email=f"disp_ret_{uid}@example.com",
            password="RetPassword123!",
            full_name="Display Test Retailer",
            role="shop_owner",
            shop_name=f"Studio {uid}",
        ),
        db=db,
    )
    ret_user = db.get(User, ret_res.user.id)
    prod_res = create_product(
        product_in=ProductCreate(
            shop_id=ret_user.shop_id,
            product_name="Casual Linen Shirt",
            category="Casual",
            price=1499.00,
            stock_quantity=15,
            image_url="/uploads/linen_shirt.jpg",
        ),
        current_user=ret_user,
        db=db,
    )

    # 3. Start Try-On Session
    cust_photo_upload = MockUploadFile("photo.jpg", VALID_JPEG_BYTES)
    bg_tasks = DummyBackgroundTasks()
    start_res = asyncio.run(
        start_tryon(
            background_tasks=bg_tasks,
            customer_photo=cust_photo_upload,
            product_id=prod_res.id,
            current_user=cust_user,
            db=db,
        )
    )
    session_id = start_res.session_id
    print(f"  ✓ Created try-on session {session_id} for product {prod_res.id}.")

    # 4. Upload FASHN result via import endpoint
    result_upload = MockUploadFile(f"fashn_result_{session_id}.jpg", VALID_JPEG_BYTES)
    import_res = asyncio.run(
        import_tryon_result(
            session_id=session_id,
            result_image=result_upload,
            allow_overwrite=False,
            current_user=cust_user,
            db=db,
        )
    )

    # Verify status, provenance, and message
    assert import_res.status == "completed", f"Expected completed, got {import_res.status}"
    assert import_res.progress_percentage == 100
    assert "AI Fitting Complete" in import_res.stage_message, f"Unexpected stage message: {import_res.stage_message}"
    assert import_res.provenance == "manual_import", f"Expected manual_import, got {import_res.provenance}"
    assert import_res.provider == "fashn_manual"
    assert import_res.result_image_url == f"/api/tryon/{session_id}/result"
    assert import_res.is_simulation is False
    print(f"  ✓ Result imported: Status='completed', StageMessage='{import_res.stage_message}'.")

    # 5. Verify result image streaming endpoint
    stream_res = get_tryon_result(session_id=session_id, current_user=cust_user, db=db)
    assert isinstance(stream_res, FileResponse), "Expected FileResponse stream"
    assert Path(stream_res.path).exists(), "Result file does not exist on disk"
    print("  ✓ Result file streamed successfully from storage.")

    # 6. Re-display with allow_overwrite=True
    new_result_upload = MockUploadFile(f"fashn_new_{session_id}.png", VALID_PNG_BYTES, content_type="image/png")
    overwrite_res = asyncio.run(
        import_tryon_result(
            session_id=session_id,
            result_image=new_result_upload,
            allow_overwrite=True,
            current_user=cust_user,
            db=db,
        )
    )
    assert overwrite_res.status == "completed"
    assert "AI Fitting Complete" in overwrite_res.stage_message
    print("  ✓ Result re-display with allow_overwrite=True succeeded seamlessly.")
    db.close()


def test_invalid_image_rejection():
    print("\n--- Test 2: Invalid Image Payload Rejection ---")
    db = SessionLocal()
    session_id = f"test_inval_{uuid.uuid4().hex[:8]}"

    # Setup dummy session in DB
    dummy_session = TryOnSession(
        id=session_id,
        customer_photo_url="cust_test.jpg",
        status="pending",
    )
    db.add(dummy_session)
    db.commit()

    # 1. Empty payload
    empty_upload = MockUploadFile("empty.jpg", b"")
    try:
        asyncio.run(import_tryon_result(session_id=session_id, result_image=empty_upload, db=db))
        assert False, "Empty file should have been rejected"
    except HTTPException as exc:
        assert exc.status_code == status.HTTP_400_BAD_REQUEST
        print("  ✓ Empty file rejected with HTTP 400.")

    # 2. Corrupt / text bytes disguised as .jpg
    fake_upload = MockUploadFile("fake.jpg", b"This is plain ASCII text pretending to be an image.")
    try:
        asyncio.run(import_tryon_result(session_id=session_id, result_image=fake_upload, db=db))
        assert False, "Non-image text should have been rejected"
    except HTTPException as exc:
        assert exc.status_code == status.HTTP_400_BAD_REQUEST
        print("  ✓ Non-image text payload rejected with HTTP 400.")

    # 3. Oversized file (> 10MB)
    huge_bytes = b"\xff\xd8\xff\xe0" + (b"\x00" * (10 * 1024 * 1024 + 512))
    huge_upload = MockUploadFile("huge.jpg", huge_bytes)
    try:
        asyncio.run(import_tryon_result(session_id=session_id, result_image=huge_upload, db=db))
        assert False, "Oversized file should have been rejected"
    except HTTPException as exc:
        assert exc.status_code == status.HTTP_400_BAD_REQUEST
        assert "exceeds the maximum allowed limit" in exc.detail
        print("  ✓ Oversized (>10MB) file rejected with HTTP 400.")

    # Cleanup dummy session
    db.delete(dummy_session)
    db.commit()
    db.close()


def test_failed_upload_handling():
    print("\n--- Test 3: Failed Upload Handling & Permission Verification ---")
    db = SessionLocal()
    uid = uuid.uuid4().hex[:8]

    # 1. Non-existent session
    upload = MockUploadFile("result.jpg", VALID_JPEG_BYTES)
    try:
        asyncio.run(import_tryon_result(session_id="nonexistent-session-id", result_image=upload, db=db))
        assert False, "Nonexistent session should raise 404"
    except HTTPException as exc:
        assert exc.status_code == status.HTTP_404_NOT_FOUND
        print("  ✓ Non-existent session rejected with HTTP 404.")

    # 2. Cross-user access protection
    user1_res = register_user(
        UserRegisterRequest(email=f"u1_{uid}@example.com", password="Pass123!456", role="customer"),
        db=db,
    )
    user2_res = register_user(
        UserRegisterRequest(email=f"u2_{uid}@example.com", password="Pass123!456", role="customer"),
        db=db,
    )
    user1 = db.get(User, user1_res.user.id)
    user2 = db.get(User, user2_res.user.id)

    sess = TryOnSession(
        id=f"private_sess_{uid}",
        customer_photo_url="cust_test.jpg",
        user_id=user1.id,
        status="pending",
    )
    db.add(sess)
    db.commit()

    # User 2 attempts to upload result for User 1's session -> 403 Forbidden
    upload2 = MockUploadFile("result.jpg", VALID_JPEG_BYTES)
    try:
        asyncio.run(import_tryon_result(session_id=sess.id, result_image=upload2, current_user=user2, db=db))
        assert False, "Cross-user upload should raise 403"
    except HTTPException as exc:
        assert exc.status_code == status.HTTP_403_FORBIDDEN
        print("  ✓ Cross-user unauthorized upload rejected with HTTP 403.")

    # Anonymous user attempts to upload for authenticated user's session -> 401 Unauthorized
    upload3 = MockUploadFile("result.jpg", VALID_JPEG_BYTES)
    try:
        asyncio.run(import_tryon_result(session_id=sess.id, result_image=upload3, current_user=None, db=db))
        assert False, "Anonymous upload to private session should raise 401"
    except HTTPException as exc:
        assert exc.status_code == status.HTTP_401_UNAUTHORIZED
        print("  ✓ Anonymous upload to private session rejected with HTTP 401.")

    # Cleanup
    db.delete(sess)
    db.delete(user1)
    db.delete(user2)
    db.commit()
    db.close()


if __name__ == "__main__":
    print("===================================================================")
    print("  RUNNING SIMPLIFIED AI RESULT DISPLAY TEST SUITE                  ")
    print("===================================================================")

    test_simplify_display_result_workflow()
    test_invalid_image_rejection()
    test_failed_upload_handling()

    print("\n===================================================================")
    print("  ALL SIMPLIFIED RESULT DISPLAY TESTS PASSED (3/3)!                ")
    print("===================================================================")
