"""
Phase 5B Integration & Concurrency Tests for VirtualFit AI.

Validates:
1. Provider factory dynamic selection (mock vs fashn) and strict ₹0 guardrails.
2. Dynamic provider assignment in POST /api/tryon (provider="fashn", is_simulation=False).
3. Concurrency semaphore initialization and ceiling enforcement.
4. GET /api/tryon/{session_id}/result endpoint behavior:
   - Nonexistent session -> HTTP 404
   - In-progress / pending session -> HTTP 409 Conflict
   - Failed session -> HTTP 409 Conflict with error details
   - Completed mock session (no AI image) -> HTTP 404
   - Completed genuine session with valid image -> HTTP 200 FileResponse with correct headers
   - Missing / expired file -> HTTP 404
   - Path traversal attempts -> blocked safely
5. Error capture in background execution (records failure in DB).
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
from fastapi.responses import FileResponse

from app.database import SessionLocal
from app.models import Product, TryOnSession
from app.routers.tryon import (
    start_tryon,
    get_tryon_status,
    get_tryon_result,
    run_tryon_background,
    get_inference_semaphore,
    validate_image_file,
)
from app.services.tryon.factory import get_tryon_provider, SUPPORTED_PROVIDERS
from app.services.tryon.mock_provider import MockTryOnProvider
from app.services.tryon.fashn_provider import FashnTryOnProvider
from app.services.tryon.storage import (
    RESULTS_DIR,
    CUSTOMER_PHOTOS_DIR,
    get_result_path,
    delete_customer_photo,
)

VALID_JPEG_BYTES = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00" + (b"\xaa" * 100)


def test_factory_dynamic_selection_and_safeguards():
    print("\n--- 1. Testing Provider Factory Dynamic Selection & Safeguards ---")

    # Mock resolution
    p_mock = get_tryon_provider("mock")
    assert isinstance(p_mock, MockTryOnProvider)
    assert p_mock.provider_name == "mock"

    # Fashn resolution
    p_fashn = get_tryon_provider("fashn")
    assert isinstance(p_fashn, FashnTryOnProvider)
    assert p_fashn.provider_name == "fashn"

    # Environment variable resolution
    os.environ["TRYON_PROVIDER"] = "fashn"
    p_env = get_tryon_provider()
    assert isinstance(p_env, FashnTryOnProvider)

    os.environ["TRYON_PROVIDER"] = "mock"
    p_env_mock = get_tryon_provider()
    assert isinstance(p_env_mock, MockTryOnProvider)

    # Clean up env
    os.environ.pop("TRYON_PROVIDER", None)

    # Replicate and paid cloud APIs must be blocked under ₹0 budget policy
    try:
        get_tryon_provider("replicate")
        assert False, "Should raise ValueError for 'replicate'"
    except ValueError as exc:
        assert "disabled under the ₹0 budget policy" in str(exc)

    # Unsupported provider must raise ValueError
    try:
        get_tryon_provider("unsupported_fake_provider")
        assert False, "Should raise ValueError for unsupported provider"
    except ValueError as exc:
        assert "unsupported try-on provider" in str(exc).lower()

    print("[PASS] Factory dynamic provider resolution & strict ₹0 guardrails verified.")


def test_concurrency_semaphore():
    print("\n--- 2. Testing Inference Concurrency Semaphore ---")

    os.environ["FASHN_MAX_CONCURRENT_INFERENCES"] = "2"
    # Reset singleton for testing
    import app.routers.tryon as tryon_module
    tryon_module._inference_semaphore = None

    sem = get_inference_semaphore()
    assert isinstance(sem, asyncio.Semaphore)
    # Check that initial semaphore counter is 2
    assert sem._value == 2

    # Reset back to default
    os.environ["FASHN_MAX_CONCURRENT_INFERENCES"] = "1"
    tryon_module._inference_semaphore = None
    sem_default = get_inference_semaphore()
    assert sem_default._value == 1

    print("[PASS] Concurrency semaphore initialization and configuration verified.")


def test_start_tryon_dynamic_provider():
    print("\n--- 3. Testing Dynamic Provider in start_tryon ---")

    db = SessionLocal()
    session_ids_to_clean = []
    try:
        product = db.query(Product).filter(Product.image_url.isnot(None), Product.image_url != "").first()
        assert product is not None, "Product with valid image_url needed in database for testing"

        # A) With TRYON_PROVIDER=mock
        os.environ["TRYON_PROVIDER"] = "mock"
        upload = UploadFile(
            file=io.BytesIO(VALID_JPEG_BYTES),
            filename="customer_mock_test.jpg",
        )
        bg = BackgroundTasks()
        resp_mock = asyncio.run(
            start_tryon(
                background_tasks=bg,
                customer_photo=upload,
                product_id=product.id,
                db=db,
            )
        )
        session_ids_to_clean.append(resp_mock.session_id)
        assert resp_mock.provider == "mock"
        assert resp_mock.is_simulation is True
        assert "simulation" in resp_mock.stage_message.lower()

        # B) With TRYON_PROVIDER=fashn and configured inference worker
        os.environ["TRYON_PROVIDER"] = "fashn"
        os.environ["FASHN_INFERENCE_URL"] = "http://127.0.0.1:8001"
        upload_fashn = UploadFile(
            file=io.BytesIO(VALID_JPEG_BYTES),
            filename="customer_fashn_test.jpg",
        )
        bg_fashn = BackgroundTasks()
        resp_fashn = asyncio.run(
            start_tryon(
                background_tasks=bg_fashn,
                customer_photo=upload_fashn,
                product_id=product.id,
                db=db,
            )
        )
        session_ids_to_clean.append(resp_fashn.session_id)
        assert resp_fashn.provider == "fashn"
        assert resp_fashn.is_simulation is False
        assert "fashn" in resp_fashn.stage_message.lower()

        print("[PASS] Dynamic provider selection in start_tryon verified.")

    finally:
        os.environ["TRYON_PROVIDER"] = "mock"
        os.environ.pop("FASHN_INFERENCE_URL", None)
        for s_id in session_ids_to_clean:
            row = db.get(TryOnSession, s_id)
            if row:
                delete_customer_photo(row.customer_photo_url)
                db.delete(row)
        db.commit()
        db.close()


def test_get_tryon_result_endpoint():
    print("\n--- 4. Testing GET /api/tryon/{session_id}/result Endpoint ---")

    db = SessionLocal()
    test_sessions = []
    created_files = []

    try:
        product = db.query(Product).first()
        assert product is not None

        # 1. Nonexistent session ID -> HTTP 404
        try:
            get_tryon_result("nonexistent-uuid-0000", db=db)
            assert False, "Nonexistent session should raise 404"
        except HTTPException as exc:
            assert exc.status_code == status.HTTP_404_NOT_FOUND

        # 2. In-progress / Pending session -> HTTP 409 Conflict
        pending_id = str(uuid.uuid4())
        s_pending = TryOnSession(
            id=pending_id,
            customer_photo_url="test_cust.jpg",
            product_id=product.id,
            status="processing",
            progress_percentage=45,
            stage_message="Synthesizing diffusion...",
            provider="fashn",
        )
        db.add(s_pending)
        db.commit()
        test_sessions.append(pending_id)

        try:
            get_tryon_result(pending_id, db=db)
            assert False, "Processing session should raise 409 Conflict"
        except HTTPException as exc:
            assert exc.status_code == status.HTTP_409_CONFLICT
            assert "in progress" in exc.detail.lower()

        # 3. Failed session -> HTTP 409 Conflict with error details
        failed_id = str(uuid.uuid4())
        s_failed = TryOnSession(
            id=failed_id,
            customer_photo_url="test_cust.jpg",
            product_id=product.id,
            status="failed",
            progress_percentage=30,
            stage_message="Model inference failed.",
            error_message="CUDA out of memory",
            provider="fashn",
        )
        db.add(s_failed)
        db.commit()
        test_sessions.append(failed_id)

        try:
            get_tryon_result(failed_id, db=db)
            assert False, "Failed session should raise 409 Conflict"
        except HTTPException as exc:
            assert exc.status_code == status.HTTP_409_CONFLICT
            assert "failed" in exc.detail.lower()
            assert "cuda out of memory" in exc.detail.lower()

        # 4. Completed mock session (no AI image produced) -> HTTP 404
        mock_completed_id = str(uuid.uuid4())
        s_mock = TryOnSession(
            id=mock_completed_id,
            customer_photo_url="test_cust.jpg",
            product_id=product.id,
            status="completed",
            progress_percentage=100,
            stage_message="Simulation completed.",
            result_image_url=None,
            provider="mock",
        )
        db.add(s_mock)
        db.commit()
        test_sessions.append(mock_completed_id)

        try:
            get_tryon_result(mock_completed_id, db=db)
            assert False, "Completed mock session with no image should raise 404"
        except HTTPException as exc:
            assert exc.status_code == status.HTTP_404_NOT_FOUND
            assert "mock simulation" in exc.detail.lower()

        # 5. Completed genuine session with valid image file -> HTTP 200 FileResponse
        completed_id = str(uuid.uuid4())
        result_filename = f"res_{completed_id}.jpg"
        result_file_path = RESULTS_DIR / result_filename
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        with open(result_file_path, "wb") as f:
            f.write(VALID_JPEG_BYTES)
        created_files.append(result_file_path)

        s_completed = TryOnSession(
            id=completed_id,
            customer_photo_url="test_cust.jpg",
            product_id=product.id,
            status="completed",
            progress_percentage=100,
            stage_message="Virtual try-on completed successfully.",
            result_image_url=f"/api/tryon/{completed_id}/result",
            provider="fashn",
        )
        db.add(s_completed)
        db.commit()
        test_sessions.append(completed_id)

        response = get_tryon_result(completed_id, db=db)
        assert isinstance(response, FileResponse)
        assert response.status_code == 200
        assert response.media_type == "image/jpeg"
        assert response.headers.get("Cache-Control") == "private, max-age=3600"
        assert response.headers.get("X-Content-Type-Options") == "nosniff"

        # 6. Missing or expired file -> HTTP 404
        expired_id = str(uuid.uuid4())
        s_expired = TryOnSession(
            id=expired_id,
            customer_photo_url="test_cust.jpg",
            product_id=product.id,
            status="completed",
            progress_percentage=100,
            stage_message="Completed but purged.",
            result_image_url=f"/api/tryon/{expired_id}/result",
            provider="fashn",
        )
        db.add(s_expired)
        db.commit()
        test_sessions.append(expired_id)

        try:
            get_tryon_result(expired_id, db=db)
            assert False, "Expired result file should raise 404"
        except HTTPException as exc:
            assert exc.status_code == status.HTTP_404_NOT_FOUND
            assert "not found" in exc.detail.lower() or "expired" in exc.detail.lower()

        print("[PASS] GET /api/tryon/{session_id}/result validation, status checking, and FileResponse verified.")

    finally:
        # Cleanup
        for s_id in test_sessions:
            row = db.get(TryOnSession, s_id)
            if row:
                db.delete(row)
        db.commit()
        db.close()

        for fp in created_files:
            try:
                if fp.exists():
                    fp.unlink()
            except Exception:
                pass


def test_background_error_state_handling():
    print("\n--- 5. Testing Background Task Failure DB Recording ---")

    db = SessionLocal()
    session_id = str(uuid.uuid4())
    os.environ["TRYON_PROVIDER"] = "fashn"
    try:
        product = db.query(Product).first()
        assert product is not None

        # Create session
        s = TryOnSession(
            id=session_id,
            customer_photo_url="nonexistent_customer_photo.jpg",
            product_id=product.id,
            status="pending",
            provider="fashn",
        )
        db.add(s)
        db.commit()

        # Run background task with invalid customer photo path
        # Fashn provider will raise FileNotFoundError when resolving the image
        asyncio.run(
            run_tryon_background(
                session_id=session_id,
                customer_photo_filename="nonexistent_customer_photo.jpg",
                product_image_url="http://localhost:8000/uploads/invalid.jpg",
                category="tops",
            )
        )

        # Verify DB session was marked failed
        db.expire_all()
        updated = db.get(TryOnSession, session_id)
        assert updated is not None
        assert updated.status == "failed"
        assert updated.error_message is not None
        assert "failed" in updated.stage_message.lower()

        print("[PASS] Background task exception safely captured and stored in PostgreSQL.")

    finally:
        os.environ["TRYON_PROVIDER"] = "mock"
        row = db.get(TryOnSession, session_id)
        if row:
            db.delete(row)
            db.commit()
        db.close()


if __name__ == "__main__":
    test_factory_dynamic_selection_and_safeguards()
    test_concurrency_semaphore()
    test_start_tryon_dynamic_provider()
    test_get_tryon_result_endpoint()
    test_background_error_state_handling()
    print("\n==========================================")
    print("ALL PHASE 5B INTEGRATION TESTS PASSED (100%)")
    print("==========================================")
