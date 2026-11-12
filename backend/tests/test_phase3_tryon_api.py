"""
Automated validation tests for Phase 3:
- Try-On router endpoints: POST /api/tryon and GET /api/tryon/{session_id}
- Image content magic byte validation (JPEG, PNG, WebP vs invalid/oversized/empty)
- Product verification (nonexistent product -> 404, product without usable image -> 400)
- Asynchronous background task execution and DB session lifecycle isolation
- Verification that customer photo paths and binaries are never exposed in API responses
- Explicit mock simulation notice on completed sessions
"""
import io
import os
import sys
import uuid
import asyncio
from pathlib import Path

# Add backend root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import HTTPException, BackgroundTasks, UploadFile, status
from app.database import SessionLocal
from app.models import Product, TryOnSession
from app.routers.tryon import (
    start_tryon,
    get_tryon_status,
    validate_image_file,
    run_tryon_background,
    MAX_UPLOAD_SIZE_BYTES,
)
from app.services.tryon.storage import (
    CUSTOMER_PHOTOS_DIR,
    delete_customer_photo,
)

# Standard mock image payloads
VALID_JPEG_BYTES = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00" + (b"\xaa" * 100)
VALID_PNG_BYTES = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + (b"\xbb" * 100)
VALID_WEBP_BYTES = b"RIFF\x24\x00\x00\x00WEBPVP8 " + (b"\xcc" * 100)


def test_image_validation_magic_bytes():
    print("\n--- Testing Magic Byte Image Validation ---")
    # Valid formats
    assert validate_image_file(VALID_JPEG_BYTES, "test.jpg") == ".jpg"
    assert validate_image_file(VALID_PNG_BYTES, "test.png") == ".png"
    assert validate_image_file(VALID_WEBP_BYTES, "test.webp") == ".webp"

    # Reject empty
    try:
        validate_image_file(b"", "empty.jpg")
        assert False, "Empty file should raise HTTPException(400)"
    except HTTPException as exc:
        assert exc.status_code == status.HTTP_400_BAD_REQUEST
        assert "empty" in exc.detail.lower()

    # Reject unsupported format (e.g. GIF or plain text)
    try:
        validate_image_file(b"GIF89a\x01\x00\x01\x00\x80\x00\x00", "image.gif")
        assert False, "GIF format should be rejected"
    except HTTPException as exc:
        assert exc.status_code == status.HTTP_400_BAD_REQUEST
        assert "unsupported" in exc.detail.lower()

    # Reject fake extension (text file renamed to .jpg)
    try:
        validate_image_file(b"<!DOCTYPE html><html><body>Fake</body></html>", "fake.jpg")
        assert False, "Non-image disguised as .jpg should be rejected"
    except HTTPException as exc:
        assert exc.status_code == status.HTTP_400_BAD_REQUEST

    # Reject oversized
    try:
        oversized = b"\xff\xd8\xff" + (b"\x00" * (MAX_UPLOAD_SIZE_BYTES + 1024))
        validate_image_file(oversized, "big.jpg")
        assert False, "Oversized file should raise HTTPException(400)"
    except HTTPException as exc:
        assert exc.status_code == status.HTTP_400_BAD_REQUEST
        assert "exceeds" in exc.detail.lower()

    print("[PASS] Image content magic byte validation verified.")


async def _run_async_api_tests():
    print("\n--- Testing Try-On Endpoints (POST /api/tryon & GET /api/tryon/{id}) ---")
    os.environ["TRYON_PROVIDER"] = "mock"
    if SessionLocal is None:
        print("Database not configured, skipping DB integration tests.")
        return

    db = SessionLocal()
    created_sessions = []
    temp_products = []

    try:
        # Find an existing product with a valid image_url
        valid_product = db.query(Product).filter(Product.image_url.isnot(None), Product.image_url != "").first()
        assert valid_product is not None, "At least one product with image_url required in DB"
        prod_id = valid_product.id

        # -------------------------------------------------------------
        # Test 1: POST /api/tryon - Valid Submission (202 Accepted)
        # -------------------------------------------------------------
        bg_tasks = BackgroundTasks()
        photo_upload = UploadFile(
            file=io.BytesIO(VALID_JPEG_BYTES),
            filename="customer_selfie.jpg",
        )

        resp = await start_tryon(
            background_tasks=bg_tasks,
            customer_photo=photo_upload,
            product_id=prod_id,
            db=db,
        )

        assert resp.status == "pending"
        assert resp.progress_percentage == 0
        assert resp.provider == "mock"
        assert resp.is_simulation is True
        assert resp.product_id == prod_id
        assert resp.session_id is not None
        created_sessions.append(resp.session_id)

        # Verify privacy: response MUST NOT contain customer_photo_url or internal storage path
        resp_dict = resp.model_dump()
        assert "customer_photo_url" not in resp_dict
        assert "storage" not in str(resp_dict)

        print(f"[PASS] POST /api/tryon accepted session: {resp.session_id} (HTTP 202)")

        # -------------------------------------------------------------
        # Test 2: Background Task Execution
        # -------------------------------------------------------------
        assert len(bg_tasks.tasks) >= 1, "Background tasks must have at least the try-on task scheduled"

        # Execute scheduled background tasks
        for task in bg_tasks.tasks:
            if asyncio.iscoroutinefunction(task.func):
                await task.func(*task.args, **task.kwargs)
            else:
                task.func(*task.args, **task.kwargs)

        # -------------------------------------------------------------
        # Test 3: GET /api/tryon/{session_id} - Poll Completed Task
        # -------------------------------------------------------------
        db.expire_all()
        status_resp = get_tryon_status(session_id=resp.session_id, db=db)

        assert status_resp.session_id == resp.session_id
        assert status_resp.product_id == prod_id
        assert status_resp.status == "completed"
        assert status_resp.progress_percentage == 100
        assert status_resp.provider == "mock"
        assert status_resp.is_simulation is True
        assert status_resp.result_image_url is None, "Must be None: mock should never return a fake fitting image"

        # Explicit simulation notice check
        expected_notice = "Simulation completed. No AI-generated fitting image was produced."
        assert status_resp.stage_message == expected_notice
        assert status_resp.message == expected_notice

        # Confirm customer photo stays in private storage and not in public uploads
        db_record = db.get(TryOnSession, resp.session_id)
        assert db_record is not None
        assert db_record.customer_photo_url.startswith("cust_")
        private_photo_path = CUSTOMER_PHOTOS_DIR / db_record.customer_photo_url
        assert private_photo_path.exists(), "Customer photo must reside in private storage"
        assert "uploads" not in str(private_photo_path), "Customer photo must not reside in public uploads"

        print(f"[PASS] GET /api/tryon/{resp.session_id} returned completed status with explicit simulation notice.")

        # -------------------------------------------------------------
        # Test 4: GET /api/tryon/{nonexistent_id} -> 404 Not Found
        # -------------------------------------------------------------
        fake_id = str(uuid.uuid4())
        try:
            get_tryon_status(session_id=fake_id, db=db)
            assert False, "Nonexistent session_id should raise HTTPException(404)"
        except HTTPException as exc:
            assert exc.status_code == status.HTTP_404_NOT_FOUND
            assert fake_id in exc.detail

        print("[PASS] GET /api/tryon/{invalid_id} returned HTTP 404.")

        # -------------------------------------------------------------
        # Test 5: POST /api/tryon with nonexistent product_id -> 404
        # -------------------------------------------------------------
        try:
            nonexistent_prod_id = 999999
            await start_tryon(
                background_tasks=BackgroundTasks(),
                customer_photo=UploadFile(file=io.BytesIO(VALID_JPEG_BYTES), filename="photo.jpg"),
                product_id=nonexistent_prod_id,
                db=db,
            )
            assert False, "Nonexistent product_id should raise HTTPException(404)"
        except HTTPException as exc:
            assert exc.status_code == status.HTTP_404_NOT_FOUND
            assert "not found" in exc.detail.lower()

        print("[PASS] POST /api/tryon with nonexistent product returned HTTP 404.")

        # -------------------------------------------------------------
        # Test 6: POST /api/tryon with product missing image_url -> 400
        # -------------------------------------------------------------
        imageless_prod = Product(
            shop_id=valid_product.shop_id,
            product_name="Product Without Image",
            price=999.00,
            stock_quantity=10,
            image_url="",  # Empty image URL
            is_available=True,
        )
        db.add(imageless_prod)
        db.commit()
        db.refresh(imageless_prod)
        temp_products.append(imageless_prod.id)

        try:
            await start_tryon(
                background_tasks=BackgroundTasks(),
                customer_photo=UploadFile(file=io.BytesIO(VALID_JPEG_BYTES), filename="photo.jpg"),
                product_id=imageless_prod.id,
                db=db,
            )
            assert False, "Product without image should raise HTTPException(400)"
        except HTTPException as exc:
            assert exc.status_code == status.HTTP_400_BAD_REQUEST
            assert "does not have a usable image" in exc.detail

        print("[PASS] POST /api/tryon with imageless product returned HTTP 400.")

    finally:
        # Cleanup test sessions and customer photos
        for s_id in created_sessions:
            try:
                row = db.get(TryOnSession, s_id)
                if row:
                    if row.customer_photo_url:
                        delete_customer_photo(row.customer_photo_url)
                    db.delete(row)
                    db.commit()
            except Exception:
                db.rollback()

        # Cleanup temp products
        for p_id in temp_products:
            try:
                p_row = db.get(Product, p_id)
                if p_row:
                    db.delete(p_row)
                    db.commit()
            except Exception:
                db.rollback()

        db.close()


def test_tryon_endpoints():
    asyncio.run(_run_async_api_tests())


if __name__ == "__main__":
    test_image_validation_magic_bytes()
    test_tryon_endpoints()
    print("\n==========================================")
    print("ALL PHASE 3 API TESTS PASSED (100%)")
    print("==========================================")

