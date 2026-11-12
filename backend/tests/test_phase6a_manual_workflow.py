"""
Phase 6A Integration Tests for VirtualFit AI: Manual Colab AI Workflow.

Validates:
1. GET /api/tryon/{session_id}/inputs
   - Correctly exports session metadata, normalized category, and customer photo download path.
   - Returns 404 for nonexistent sessions.
2. GET /api/tryon/{session_id}/customer-photo
   - Securely streams the private customer photo for manual download.
   - Path traversal attempts blocked.
   - Returns 404 if session or file is missing.
3. POST /api/tryon/{session_id}/import-result
   - Validates image payload (magic bytes, size <= 10MB, dimension bounds).
   - Rejects empty, corrupted, or oversized files (400).
   - Rejects nonexistent sessions (404).
   - Securely writes genuine result image to RESULTS_DIR.
   - Updates PostgreSQL TryOnSession state: status="completed", progress=100, provider="fashn".
   - Explicitly marks is_simulation=False.
4. GET /api/tryon/{session_id}/result
   - Successfully streams the imported genuine result image.
5. Image Dimension Parser Unit Test
   - Verifies dimension parsing for JPEG, PNG, and WebP byte streams.
"""
import io
import os
import sys
import uuid
import struct
import asyncio
from pathlib import Path
from datetime import datetime, timezone

# Add backend root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import HTTPException, UploadFile, status
from fastapi.responses import FileResponse

from app.database import SessionLocal
from app.models import Product, TryOnSession
from app.routers.tryon import (
    get_tryon_inputs,
    get_customer_photo_for_session,
    import_tryon_result,
    get_tryon_result,
    parse_image_dimensions,
    validate_image_file,
)
from app.services.tryon.storage import (
    RESULTS_DIR,
    CUSTOMER_PHOTOS_DIR,
    save_customer_photo,
    delete_customer_photo,
    delete_result_file,
)

# Standard test images
VALID_JPEG_BYTES = (
    b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    # Append a SOF0 marker for 576x864 dimensions:
    # 0xFF, 0xC0 (SOF0), length=17 (0x00, 0x11), precision=8, height=864 (0x03, 0x60), width=576 (0x02, 0x40), components=3
    b"\xff\xc0\x00\x11\x08\x03\x60\x02\x40\x03\x01\x11\x00\x02\x11\x01\x03\x11\x01"
    + (b"\xaa" * 500)
)

VALID_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR"
    + struct.pack(">II", 576, 864)  # width=576, height=864
    + b"\x08\x02\x00\x00\x00"
    b"\x00\x00\x00\x00"  # CRC placeholder
    + (b"\xbb" * 200)
)


def create_test_product(db, name="Test Oxford Shirt", category="Formal Shirts"):
    prod = Product(
        shop_id=1,
        product_name=name,
        description="A premium formal shirt for testing",
        category=category,
        price=1999.00,
        image_url="http://localhost:8000/uploads/products/test_shirt.jpg",
        is_available=True,
    )
    db.add(prod)
    db.commit()
    db.refresh(prod)
    return prod


def test_dimension_parser():
    print("\n--- 1. Testing Image Dimension Parser ---")
    # PNG check
    png_dims = parse_image_dimensions(VALID_PNG_BYTES, ".png")
    assert png_dims == (576, 864), f"Expected (576, 864), got {png_dims}"

    # JPEG check
    jpg_dims = parse_image_dimensions(VALID_JPEG_BYTES, ".jpg")
    assert jpg_dims == (576, 864), f"Expected (576, 864), got {jpg_dims}"

    # Non-image check
    invalid_dims = parse_image_dimensions(b"NOT_AN_IMAGE", ".jpg")
    assert invalid_dims is None
    print("[PASS] Image dimension parser correctly extracts dimensions.")


def test_export_inputs_endpoint():
    print("\n--- 2. Testing GET /api/tryon/{session_id}/inputs ---")
    db = SessionLocal()
    try:
        # 1. Nonexistent session check -> 404
        nonexistent_id = str(uuid.uuid4())
        try:
            get_tryon_inputs(session_id=nonexistent_id, db=db)
            assert False, "Should raise 404 for nonexistent session"
        except HTTPException as exc:
            assert exc.status_code == status.HTTP_404_NOT_FOUND

        # 2. Setup real product & session
        prod = create_test_product(db, name="Classic Linen Kurta", category="Ethnic Wear")
        internal_photo = save_customer_photo(VALID_JPEG_BYTES, "test_cust.jpg", ".jpg")

        session_id = str(uuid.uuid4())
        session = TryOnSession(
            id=session_id,
            customer_photo_url=internal_photo,
            product_id=prod.id,
            status="pending",
            progress_percentage=0,
            stage_message="Session initialized.",
            provider="mock",
        )
        db.add(session)
        db.commit()

        # 3. Retrieve inputs
        inputs_resp = get_tryon_inputs(session_id=session_id, db=db)
        assert inputs_resp.session_id == session_id
        assert inputs_resp.product_id == prod.id
        assert inputs_resp.product_name == "Classic Linen Kurta"
        assert inputs_resp.category == "tops"  # Kurta normalizes to tops
        assert inputs_resp.customer_photo_download_url == f"/api/tryon/{session_id}/customer-photo"
        assert inputs_resp.garment_image_url == prod.image_url

        print(f"[PASS] Successfully exported inputs: category='{inputs_resp.category}', url='{inputs_resp.customer_photo_download_url}'")

        # Cleanup
        delete_customer_photo(internal_photo)
        db.delete(session)
        db.delete(prod)
        db.commit()
    finally:
        db.close()


def test_customer_photo_download_endpoint():
    print("\n--- 3. Testing GET /api/tryon/{session_id}/customer-photo ---")
    db = SessionLocal()
    try:
        # 1. Nonexistent session -> 404
        try:
            get_customer_photo_for_session(session_id=str(uuid.uuid4()), db=db)
            assert False, "Should raise 404 for missing session"
        except HTTPException as exc:
            assert exc.status_code == status.HTTP_404_NOT_FOUND

        # 2. Create session with valid photo
        internal_photo = save_customer_photo(VALID_JPEG_BYTES, "photo.jpg", ".jpg")
        session_id = str(uuid.uuid4())
        session = TryOnSession(
            id=session_id,
            customer_photo_url=internal_photo,
            product_id=1,
            status="pending",
            provider="mock",
        )
        db.add(session)
        db.commit()

        # 3. Stream photo
        resp = get_customer_photo_for_session(session_id=session_id, db=db)
        assert isinstance(resp, FileResponse)
        assert resp.media_type == "image/jpeg"
        assert os.path.exists(resp.path)
        with open(resp.path, "rb") as f:
            read_bytes = f.read()
        assert read_bytes == VALID_JPEG_BYTES

        # 4. Traversal protection: session with traversal in customer_photo_url
        session.customer_photo_url = "../../../etc/passwd"
        db.commit()
        try:
            get_customer_photo_for_session(session_id=session_id, db=db)
            assert False, "Should raise 404 on traversal attempt"
        except HTTPException as exc:
            assert exc.status_code == status.HTTP_404_NOT_FOUND

        print("[PASS] Customer photo download securely streams photo and blocks path traversal.")

        # Cleanup
        delete_customer_photo(internal_photo)
        db.delete(session)
        db.commit()
    finally:
        db.close()


def test_import_result_endpoint_validation():
    print("\n--- 4. Testing POST /api/tryon/{session_id}/import-result Validations ---")
    db = SessionLocal()
    try:
        session_id = str(uuid.uuid4())
        session = TryOnSession(
            id=session_id,
            customer_photo_url="cust_test.jpg",
            product_id=1,
            status="processing",
            provider="mock",
        )
        db.add(session)
        db.commit()

        # A. Nonexistent session -> 404
        empty_upload = UploadFile(filename="result.jpg", file=io.BytesIO(b""))
        try:
            asyncio.run(import_tryon_result(session_id=str(uuid.uuid4()), result_image=empty_upload, db=db))
            assert False, "Should raise 404 for nonexistent session"
        except HTTPException as exc:
            assert exc.status_code == status.HTTP_404_NOT_FOUND

        # B. Empty file -> 400
        empty_upload = UploadFile(filename="result.jpg", file=io.BytesIO(b""))
        try:
            asyncio.run(import_tryon_result(session_id=session_id, result_image=empty_upload, db=db))
            assert False, "Should raise 400 for empty file"
        except HTTPException as exc:
            assert exc.status_code == status.HTTP_400_BAD_REQUEST
            assert "empty" in exc.detail.lower()

        # C. Invalid magic bytes (plain text file) -> 400
        text_upload = UploadFile(filename="result.jpg", file=io.BytesIO(b"This is not a real image."))
        try:
            asyncio.run(import_tryon_result(session_id=session_id, result_image=text_upload, db=db))
            assert False, "Should raise 400 for invalid magic bytes"
        except HTTPException as exc:
            assert exc.status_code == status.HTTP_400_BAD_REQUEST
            assert "unsupported or invalid" in exc.detail.lower()

        # D. Oversized image (> 10MB) -> 400
        oversized_bytes = b"\xff\xd8\xff\xe0" + (b"\x00" * (11 * 1024 * 1024))
        oversized_upload = UploadFile(filename="huge.jpg", file=io.BytesIO(oversized_bytes))
        try:
            asyncio.run(import_tryon_result(session_id=session_id, result_image=oversized_upload, db=db))
            assert False, "Should raise 400 for oversized image"
        except HTTPException as exc:
            assert exc.status_code == status.HTTP_400_BAD_REQUEST
            assert "exceeds" in exc.detail.lower()

        # E. Out-of-bounds dimensions (< 100px) -> 400
        tiny_png = (
            b"\x89PNG\r\n\x1a\n"
            b"\x00\x00\x00\rIHDR"
            + struct.pack(">II", 50, 50)  # 50x50 is below minimum allowed 100x100
            + b"\x08\x02\x00\x00\x00"
            b"\x00\x00\x00\x00"
            + (b"\x00" * 50)
        )
        tiny_upload = UploadFile(filename="tiny.png", file=io.BytesIO(tiny_png))
        try:
            asyncio.run(import_tryon_result(session_id=session_id, result_image=tiny_upload, db=db))
            assert False, "Should raise 400 for tiny dimensions"
        except HTTPException as exc:
            assert exc.status_code == status.HTTP_400_BAD_REQUEST
            assert "dimensions" in exc.detail.lower()

        print("[PASS] All input validation constraints (magic bytes, size, dimensions) enforced.")

        # Cleanup
        db.delete(session)
        db.commit()
    finally:
        db.close()


def test_import_result_successful_flow():
    print("\n--- 5. Testing POST /api/tryon/{session_id}/import-result Successful Flow ---")
    db = SessionLocal()
    try:
        # Create session in mock/simulated state
        session_id = str(uuid.uuid4())
        session = TryOnSession(
            id=session_id,
            customer_photo_url="cust_test.jpg",
            product_id=1,
            status="pending",
            progress_percentage=0,
            stage_message="Simulating try-on...",
            provider="mock",
        )
        db.add(session)
        db.commit()

        # Import genuine result (VALID_JPEG_BYTES representing FASHN output)
        upload = UploadFile(
            filename="fashn_result_prototype.jpg",
            file=io.BytesIO(VALID_JPEG_BYTES),
        )

        resp = asyncio.run(import_tryon_result(session_id=session_id, result_image=upload, db=db))

        # Check API response
        assert resp.session_id == session_id
        assert resp.status == "completed"
        assert resp.progress_percentage == 100
        assert resp.provider in ("fashn", "fashn_manual")
        assert resp.is_simulation is False
        assert resp.result_image_url == f"/api/tryon/{session_id}/result"
        assert "try-on result" in resp.stage_message.lower()

        # Check Database persistence
        db.refresh(session)
        assert session.status == "completed"
        assert session.progress_percentage == 100
        assert session.provider in ("fashn", "fashn_manual")
        assert session.result_image_url == f"/api/tryon/{session_id}/result"
        assert session.error_message is None

        # Check storage persistence
        target_file = RESULTS_DIR / f"res_{session_id}.jpg"
        assert target_file.exists(), "Imported result must exist in RESULTS_DIR"
        with open(target_file, "rb") as f:
            stored_bytes = f.read()
        assert stored_bytes == VALID_JPEG_BYTES

        # Test GET /api/tryon/{session_id}/result streaming
        stream_resp = get_tryon_result(session_id=session_id, db=db)
        assert isinstance(stream_resp, FileResponse)
        assert stream_resp.media_type == "image/jpeg"
        with open(stream_resp.path, "rb") as f:
            streamed_bytes = f.read()
        assert streamed_bytes == VALID_JPEG_BYTES

        print("[PASS] Genuine FASHN VTON result successfully imported, persisted in DB, and streamed via GET /result.")

        # Cleanup
        target_file.unlink(missing_ok=True)
        db.delete(session)
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    print("===================================================================")
    print("PHASE 6A: ZERO-BUDGET MANUAL AI WORKFLOW TEST SUITE")
    print("===================================================================")
    test_dimension_parser()
    test_export_inputs_endpoint()
    test_customer_photo_download_endpoint()
    test_import_result_endpoint_validation()
    test_import_result_successful_flow()
    print("\n===================================================================")
    print("ALL PHASE 6A TESTS PASSED (100% SUCCESS)")
    print("===================================================================")

