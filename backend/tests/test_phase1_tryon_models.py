"""
Automated validation tests for Phase 1: TryOnSession model & Pydantic schemas alignment.
Tests schema validation, PostgreSQL persistence, product_id foreign key, and response serialization.
"""
import uuid
import sys
from pathlib import Path
from datetime import datetime, timezone

# Add backend root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pydantic import ValidationError

from app.database import SessionLocal
from app.models import Product, TryOnSession
from app.schemas.tryon import (
    TryOnCreateRequest,
    TryOnSessionResponse,
    TryOnStatusResponse,
)


def test_tryon_create_request_validation():
    # 1. Valid with product_id
    req1 = TryOnCreateRequest(
        customer_photo_url="https://images.unsplash.com/photo-test",
        product_id=1,
    )
    assert req1.product_id == 1
    assert req1.target_product_id == 1

    # 2. Valid with legacy garment_id
    req2 = TryOnCreateRequest(
        customer_photo_url="https://images.unsplash.com/photo-test",
        garment_id=5,
    )
    assert req2.garment_id == 5
    assert req2.target_product_id == 5

    # 3. Invalid when neither is provided
    try:
        TryOnCreateRequest(customer_photo_url="https://images.unsplash.com/photo-test")
        assert False, "Should have raised ValidationError when neither product_id nor garment_id provided"
    except ValidationError as err:
        assert "Either 'product_id' or legacy 'garment_id' must be provided" in str(err)


def test_tryon_status_response_fields():
    # Test with stage_message syncing to message
    resp1 = TryOnStatusResponse(
        session_id=str(uuid.uuid4()),
        status="processing",
        progress_percentage=45,
        stage_message="Warping garment onto silhouette...",
        provider="mock",
        product_id=1,
    )
    assert resp1.progress_percentage == 45
    assert resp1.stage_message == "Warping garment onto silhouette..."
    assert resp1.message == "Warping garment onto silhouette..."
    assert resp1.provider == "mock"
    assert resp1.product_id == 1

    # Test with legacy message syncing to stage_message
    resp2 = TryOnStatusResponse(
        session_id=str(uuid.uuid4()),
        status="completed",
        progress_percentage=100,
        message="Try-on completed successfully",
        provider="fashn",
        product_id=1,
        result_image_url="https://images.unsplash.com/photo-result",
    )
    assert resp2.progress_percentage == 100
    assert resp2.stage_message == "Try-on completed successfully"
    assert resp2.message == "Try-on completed successfully"
    assert resp2.result_image_url == "https://images.unsplash.com/photo-result"


def test_database_session_creation_and_serialization():
    if SessionLocal is None:
        print("Database not configured, skipping DB integration test.")
        return

    db = SessionLocal()
    session_id = str(uuid.uuid4())
    try:
        # Find first existing product
        first_product = db.query(Product).first()
        assert first_product is not None, "At least one product should exist in DB"
        prod_id = first_product.id

        # Create TryOnSession referencing real products.id
        session = TryOnSession(
            id=session_id,
            customer_photo_url="https://images.unsplash.com/photo-sample",
            product_id=prod_id,
            status="processing",
            progress_percentage=25,
            stage_message="Detecting body pose and landmarks...",
            provider="mock",
        )
        db.add(session)
        db.commit()

        # Query back from DB
        fetched = db.get(TryOnSession, session_id)
        assert fetched is not None
        assert fetched.product_id == prod_id
        assert fetched.product is not None
        assert fetched.product.id == prod_id
        assert fetched.progress_percentage == 25
        assert fetched.stage_message == "Detecting body pose and landmarks..."
        assert fetched.provider == "mock"

        # Serialize to TryOnSessionResponse
        serialized = TryOnSessionResponse.model_validate(fetched)
        assert serialized.id == session_id
        assert serialized.product_id == prod_id
        assert serialized.product is not None
        assert serialized.product.id == prod_id
        assert serialized.progress_percentage == 25
        assert serialized.stage_message == "Detecting body pose and landmarks..."
        assert serialized.provider == "mock"
        assert serialized.garment_id is None

        # Serialize to TryOnStatusResponse
        status_resp = TryOnStatusResponse.model_validate(fetched)
        assert status_resp.session_id == session_id
        assert status_resp.product_id == prod_id
        assert status_resp.progress_percentage == 25
        assert status_resp.stage_message == "Detecting body pose and landmarks..."
        assert status_resp.message == "Detecting body pose and landmarks..."
        assert status_resp.provider == "mock"

        print("Phase 1 database persistence & serialization test PASSED successfully!")

        # Verify ON DELETE SET NULL constraint behavior
        # Create a temporary product, attach a session, delete product, and verify session.product_id becomes None
        temp_prod = Product(
            shop_id=first_product.shop_id,
            product_name="Temporary Test Blazer",
            price=1999.00,
            stock_quantity=5,
            is_available=True,
        )
        db.add(temp_prod)
        db.commit()
        db.refresh(temp_prod)
        temp_prod_id = temp_prod.id

        temp_session_id = str(uuid.uuid4())
        temp_session = TryOnSession(
            id=temp_session_id,
            customer_photo_url="https://images.unsplash.com/photo-temp",
            product_id=temp_prod_id,
            status="pending",
        )
        db.add(temp_session)
        db.commit()

        # Delete temp_prod
        db.delete(temp_prod)
        db.commit()

        # Check temp_session: should still exist, with product_id set to None
        db.expire_all()
        persisted_session = db.get(TryOnSession, temp_session_id)
        assert persisted_session is not None, "Session should not be deleted when product is deleted"
        assert persisted_session.product_id is None, "Session.product_id should be SET NULL on product deletion"
        db.delete(persisted_session)
        db.commit()
        print("ON DELETE SET NULL verification PASSED!")
    finally:
        # Clean up test session row
        try:
            cleanup_row = db.get(TryOnSession, session_id)
            if cleanup_row:
                db.delete(cleanup_row)
                db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()


if __name__ == "__main__":
    test_tryon_create_request_validation()
    test_tryon_status_response_fields()
    test_database_session_creation_and_serialization()
    print("ALL PHASE 1 TESTS PASSED!")
