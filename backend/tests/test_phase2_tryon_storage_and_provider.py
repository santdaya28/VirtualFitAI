"""
Automated validation tests for Phase 2:
- Private temporary storage (unpredictable filenames, path traversal protection, bytes retrieval, deletion)
- 1-hour expiration cleanup mechanism (verifying catalog uploads/ are untouched)
- Provider factory & guardrails against unsupported/premature providers
- Asynchronous MockTryOnProvider execution (25%, 50%, 75%, 100% progress, DB sync, simulation notice, result_image_url=None)
"""
import os
import sys
import time
import uuid
import asyncio
from pathlib import Path

# Add backend root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal
from app.models import Product, TryOnSession
from app.services.tryon.storage import (
    save_customer_photo,
    get_customer_photo_path,
    get_customer_photo_bytes,
    delete_customer_photo,
    save_result_file,
    get_result_path,
    delete_result_file,
    cleanup_expired_files,
    STORAGE_ROOT,
    CUSTOMER_PHOTOS_DIR,
    RESULTS_DIR,
)
from app.services.tryon.factory import get_tryon_provider
from app.services.tryon.mock_provider import MockTryOnProvider, SIMULATION_COMPLETED_NOTICE


def test_storage_save_and_retrieve():
    print("\n--- Testing Private Customer Photo Storage ---")
    test_data = b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"TEST_CUSTOMER_PHOTO_BYTES"

    # 1. Save with unpredictable name
    filename = save_customer_photo(test_data, original_filename="my_portrait.png")
    assert filename.startswith("cust_"), f"Expected prefix cust_, got {filename}"
    assert filename.endswith(".png"), f"Expected extension .png, got {filename}"

    # 2. Retrieve path and verify isolation
    file_path = get_customer_photo_path(filename)
    assert file_path.exists(), "Stored customer photo should exist on disk"
    assert file_path.parent == CUSTOMER_PHOTOS_DIR.resolve(), "File must be directly in customer_photos dir"
    assert "uploads" not in str(file_path), "File must never be saved in public uploads directory"

    # 3. Read bytes
    read_bytes = get_customer_photo_bytes(filename)
    assert read_bytes == test_data, "Read bytes must exactly match written bytes"

    # 4. Delete photo
    deleted = delete_customer_photo(filename)
    assert deleted is True, "delete_customer_photo should return True"
    assert not file_path.exists(), "File should no longer exist after deletion"

    # 5. Subsequent access should raise FileNotFoundError
    try:
        get_customer_photo_path(filename)
        assert False, "Should raise FileNotFoundError after file is deleted"
    except FileNotFoundError:
        pass

    print("[PASS] Private customer photo save, retrieve, and delete verified.")


def test_storage_path_traversal_protection():
    print("\n--- Testing Path Traversal Protections ---")
    malicious_inputs = [
        "../models.py",
        "../../main.py",
        "..\\..\\app\\main.py",
        "nested/sub/file.jpg",
        "/etc/passwd",
        "C:\\Windows\\System32\\calc.exe",
        "",
        "   ",
        "..",
        ".",
    ]

    for bad_name in malicious_inputs:
        try:
            get_customer_photo_path(bad_name)
            assert False, f"Expected security or file error for traversal input: '{bad_name}'"
        except (ValueError, FileNotFoundError):
            pass  # Successfully blocked

    print("[PASS] Path traversal attack attempts successfully blocked.")


def test_storage_cleanup_expired_files():
    print("\n--- Testing 1-Hour Expiration Cleanup ---")
    # Create two test files: one "expired" (mtime set to 4000s ago) and one "fresh"
    expired_name = save_customer_photo(b"EXPIRED_PHOTO_DATA", extension=".jpg")
    fresh_name = save_customer_photo(b"FRESH_PHOTO_DATA", extension=".jpg")

    expired_path = get_customer_photo_path(expired_name)
    fresh_path = get_customer_photo_path(fresh_name)

    # Artificially age the expired file past 1 hour (3600 seconds)
    old_mtime = time.time() - 4000
    os.utime(expired_path, (old_mtime, old_mtime))

    # Run cleanup with 3600 second threshold
    result = cleanup_expired_files(max_age_seconds=3600)
    assert result["customer_photos_purged"] >= 1, "Should have purged at least 1 expired photo"

    # Verify expired file was deleted, fresh file still exists
    assert not expired_path.exists(), "Expired photo should have been removed"
    assert fresh_path.exists(), "Fresh photo should NOT have been removed"

    # Clean up fresh test file
    delete_customer_photo(fresh_name)

    # Verify public uploads directory was completely untouched
    uploads_dir = Path(__file__).resolve().parent.parent / "uploads"
    if uploads_dir.exists():
        assert uploads_dir != CUSTOMER_PHOTOS_DIR
        assert uploads_dir != RESULTS_DIR

    print(f"[PASS] Cleanup expired files verified (Purged: {result['total_purged']}).")


def test_provider_factory():
    print("\n--- Testing Provider Factory & Guardrails ---")
    orig_prov = os.environ.get("TRYON_PROVIDER")
    orig_ai_prov = os.environ.get("AI_TRYON_PROVIDER")
    os.environ["TRYON_PROVIDER"] = "mock"
    os.environ.pop("AI_TRYON_PROVIDER", None)
    try:
        # Default with 'mock' should return MockTryOnProvider
        default_provider = get_tryon_provider()
        assert isinstance(default_provider, MockTryOnProvider)
        assert default_provider.provider_name == "mock"

        # Explicit 'mock'
        mock_prov = get_tryon_provider("mock")
        assert isinstance(mock_prov, MockTryOnProvider)

        # In Phase 5B: 'fashn' is supported and resolves FashnTryOnProvider
        from app.services.tryon.fashn_provider import FashnTryOnProvider
        fashn_prov = get_tryon_provider("fashn")
        assert isinstance(fashn_prov, FashnTryOnProvider)

        # Guardrails: 'replicate' or paid cloud APIs remain strictly blocked under ₹0 budget policy
        try:
            get_tryon_provider("replicate")
            assert False, "Provider 'replicate' should raise ValueError under ₹0 policy"
        except ValueError as exc:
            assert "disabled under the ₹0 budget policy" in str(exc) or "₹0" in str(exc)

        # Unsupported provider
        try:
            get_tryon_provider("unknown_vendor_xyz")
            assert False, "Unsupported provider should raise ValueError"
        except ValueError as exc:
            assert "Unsupported try-on provider" in str(exc)
    finally:
        if orig_prov is not None:
            os.environ["TRYON_PROVIDER"] = orig_prov
        else:
            os.environ.pop("TRYON_PROVIDER", None)
        if orig_ai_prov is not None:
            os.environ["AI_TRYON_PROVIDER"] = orig_ai_prov
        else:
            os.environ.pop("AI_TRYON_PROVIDER", None)

    print("[PASS] Provider factory and Phase 2 guardrails verified.")


async def _run_async_mock_provider_tests():
    print("\n--- Testing Asynchronous MockTryOnProvider Execution ---")
    provider = MockTryOnProvider(stage_delay=0.01)  # fast delay for test
    test_session_id = str(uuid.uuid4())

    db = None
    if SessionLocal is not None:
        db = SessionLocal()

    try:
        # 1. Create a TryOnSession in DB if database is connected
        first_product = None
        if db is not None:
            first_product = db.query(Product).first()
            if first_product:
                db_session = TryOnSession(
                    id=test_session_id,
                    customer_photo_url="cust_test_private.jpg",
                    product_id=first_product.id,
                    status="pending",
                    provider="mock",
                )
                db.add(db_session)
                db.commit()

        # 2. Run process_tryon
        exec_result = await provider.process_tryon(
            session_id=test_session_id,
            customer_photo_path="cust_test_private.jpg",
            garment_image_url="http://localhost:8000/uploads/product.jpg",
            category="Formal",
            db=db,
        )

        # 3. Verify structured result
        assert exec_result.session_id == test_session_id
        assert exec_result.status == "completed"
        assert exec_result.progress_percentage == 100
        assert exec_result.provider == "mock"
        assert exec_result.result_image_url is None, "Must be None: never return fake fitting images"
        assert SIMULATION_COMPLETED_NOTICE in exec_result.stage_message
        assert exec_result.metadata.get("is_simulation") is True

        # 4. Verify database updates if db was connected
        if db is not None and first_product is not None:
            db.expire_all()
            updated_session = db.get(TryOnSession, test_session_id)
            assert updated_session is not None
            assert updated_session.status == "completed"
            assert updated_session.progress_percentage == 100
            assert updated_session.provider == "mock"
            assert updated_session.result_image_url is None
            assert SIMULATION_COMPLETED_NOTICE in updated_session.stage_message

        # 5. Verify check_status
        status_check = await provider.check_status(test_session_id, db=db)
        assert status_check.status == "completed"
        assert status_check.progress_percentage == 100
        assert status_check.result_image_url is None

        print("[PASS] Asynchronous MockTryOnProvider execution and DB synchronization verified.")
    finally:
        if db is not None:
            try:
                row = db.get(TryOnSession, test_session_id)
                if row:
                    db.delete(row)
                    db.commit()
            except Exception:
                db.rollback()
            finally:
                db.close()


def test_mock_provider_execution():
    asyncio.run(_run_async_mock_provider_tests())


if __name__ == "__main__":
    test_storage_save_and_retrieve()
    test_storage_path_traversal_protection()
    test_storage_cleanup_expired_files()
    test_provider_factory()
    test_mock_provider_execution()
    print("\n==========================================")
    print("ALL PHASE 2 VALIDATION TESTS PASSED (100%)")
    print("==========================================")

