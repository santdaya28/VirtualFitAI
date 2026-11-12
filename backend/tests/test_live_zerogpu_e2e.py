"""
VirtualFit AI — Phase 10: Live Hugging Face ZeroGPU End-to-End Integration Test.

Tests genuine neural virtual try-on inference against the live Hugging Face ZeroGPU worker:
1. Validates worker reachability and health checks (is_available).
2. Sets up test database product and session record in PostgreSQL.
3. Passes real customer photo and garment reference image.
4. Stages files to remote Space via /gradio_api/upload.
5. Submits queue job to /gradio_api/call/try_on and listens to live SSE event stream.
6. Downloads genuine generated image, validates file size, magic bytes, and dimensions.
7. Saves result to private RESULTS_DIR and marks session completed in database.
8. Verifies GET /api/tryon/{session_id}/result streams genuine result with FileResponse.
"""
import io
import os
import sys
import uuid
import asyncio
from pathlib import Path

# Add backend root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal
from app.models import Product, TryOnSession, Shop, User
from app.routers.auth import register_user
from app.routers.products import create_product
from app.routers.tryon import get_tryon_result
from app.schemas.auth import UserRegisterRequest
from app.schemas.product import ProductCreate
from app.services.tryon.storage import (
    RESULTS_DIR,
    CUSTOMER_PHOTOS_DIR,
    save_customer_photo,
    delete_customer_photo,
    delete_result_file,
)
from app.services.tryon.zerogpu_provider import (
    ZeroGPUTryOnProvider,
    detect_image_mime_and_ext,
    parse_image_dimensions,
)
from app.services.tryon.factory import get_tryon_provider
from fastapi.responses import FileResponse


def run_live_zerogpu_e2e():
    print("===================================================================")
    print("  PHASE 10: LIVE HUGGING FACE ZEROGPU END-TO-END INFERENCE TEST   ")
    print("===================================================================")

    # 1. Environment & Provider Verification
    os.environ["TRYON_PROVIDER"] = "zerogpu"
    space_url = os.getenv("ZEROGPU_API_URL", "https://fashn-ai-fashn-vton-1-5.hf.space")
    os.environ["ZEROGPU_API_URL"] = space_url

    provider = get_tryon_provider("zerogpu")
    assert isinstance(provider, ZeroGPUTryOnProvider), "Factory must resolve ZeroGPUTryOnProvider"
    print(f"[Step 1] Provider resolved: '{provider.provider_name}' (Target Space: {provider.space_url})")

    # 2. Worker Reachability Check
    is_avail, avail_msg = provider.is_available()
    print(f"[Step 2] Worker Reachability Check: is_available={is_avail}")
    print(f"         Status Message: '{avail_msg}'")
    assert is_avail is True, f"ZeroGPU Space at {space_url} must be genuinely reachable."

    # 3. Setup Test Product and Customer Photo
    db = SessionLocal()
    session_id = str(uuid.uuid4())
    customer_photo_name = None
    test_product = None
    created_user = None

    try:
        # Load sample real images
        person_source = Path("uploads/0a989e6da55a48409cc25a26d3b02b8e.jpg")
        garment_source = Path("uploads/b89ae8b935b34d1fad18f3ba7bcf86f9.jpg")

        assert person_source.exists(), f"Sample person photo not found at {person_source}"
        assert garment_source.exists(), f"Sample garment photo not found at {garment_source}"

        person_bytes = person_source.read_bytes()
        garment_bytes = garment_source.read_bytes()

        # Save customer photo to private storage
        customer_photo_name = save_customer_photo(person_bytes, "live_customer.jpg", ".jpg")
        print(f"[Step 3] Stored customer photo privately: {customer_photo_name} ({len(person_bytes)} bytes)")

        # Create test retailer and product in DB
        uid = uuid.uuid4().hex[:8]
        reg_res = register_user(
            UserRegisterRequest(
                email=f"live_retailer_{uid}@example.com",
                password="SecurePassword123!",
                full_name=f"Live Retailer {uid}",
                role="shop_owner",
                shop_name=f"Live Boutique {uid}",
            ),
            db=db,
        )
        created_user = db.query(User).filter(User.email == f"live_retailer_{uid}@example.com").first()
        shop = db.get(Shop, created_user.shop_id)

        test_product = create_product(
            ProductCreate(
                shop_id=shop.id,
                product_name=f"Live Linen Shirt {uid}",
                description="Real garment for live ZeroGPU inference test",
                price=1499.0,
                category="tops",
                stock=5,
                image_url=f"/uploads/{garment_source.name}",
            ),
            current_user=created_user,
            db=db,
        )
        print(f"[Step 4] Created test product in DB (ID: {test_product.id}, Name: '{test_product.product_name}')")

        # Create TryOnSession record
        session = TryOnSession(
            id=session_id,
            customer_photo_url=customer_photo_name,
            product_id=test_product.id,
            user_id=created_user.id,
            status="pending",
            provider="zerogpu",
            provenance="genuine_zerogpu",
            progress_percentage=0,
            stage_message="Queued for live ZeroGPU inference...",
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        print(f"[Step 5] Created TryOnSession '{session_id}' in PostgreSQL (status=pending)")

        # 4. Execute Real Neural Try-On Inference
        print("\n[Step 6] Dispatching live neural virtual try-on inference to Hugging Face ZeroGPU...")
        print("         (Staging images, queuing via SSE, executing 30-step diffusion synthesis)...")
        result = asyncio.run(
            provider.process_tryon(
                session_id=session_id,
                customer_photo_path=customer_photo_name,
                garment_image_url=f"/uploads/{garment_source.name}",
                category="tops",
                db=db,
            )
        )

        # 5. Verify Execution Result Object
        print("\n[Step 7] Validating execution result:")
        print(f"         Status: {result.status}")
        print(f"         Progress: {result.progress_percentage}%")
        print(f"         Stage Message: '{result.stage_message}'")
        print(f"         Result Image URL: {result.result_image_url}")
        print(f"         Error Message: {result.error_message}")

        assert result.status == "completed", f"Expected completed status, got {result.status} (Error: {result.error_message})"
        assert result.progress_percentage == 100, f"Expected 100%, got {result.progress_percentage}"
        assert result.result_image_url == f"/api/tryon/{session_id}/result"

        # 6. Verify Database State
        db.expire_all()
        session_row = db.get(TryOnSession, session_id)
        assert session_row is not None
        assert session_row.status == "completed"
        assert session_row.progress_percentage == 100
        assert session_row.result_image_url == f"/api/tryon/{session_id}/result"
        assert session_row.provenance in ("genuine_zerogpu", "genuine_inference")
        print("[Step 8] PostgreSQL database record verified: status=completed, provenance=genuine_zerogpu")

        # 7. Verify Result Image on Disk
        result_ext = Path(result.result_image_url).suffix or ".webp"
        res_file = RESULTS_DIR / f"res_{session_id}{result_ext}"
        if not res_file.exists():
            # Check other possible extensions
            for ext in (".webp", ".jpg", ".png"):
                alt = RESULTS_DIR / f"res_{session_id}{ext}"
                if alt.exists():
                    res_file = alt
                    break

        assert res_file.exists(), f"Result file was not saved to disk at {res_file}"
        res_bytes = res_file.read_bytes()
        res_mime, res_ext = detect_image_mime_and_ext(res_bytes)
        res_dims = parse_image_dimensions(res_bytes, res_ext)

        print(f"[Step 9] Verified generated image file on disk: {res_file.name}")
        print(f"         File Size: {len(res_bytes):,} bytes")
        print(f"         MIME Type: {res_mime} ({res_ext})")
        print(f"         Dimensions: {res_dims[0]}x{res_dims[1]} px")

        assert len(res_bytes) >= 1000, f"Result file is too small ({len(res_bytes)} bytes)"
        assert res_dims is not None and res_dims[0] >= 100 and res_dims[1] >= 100

        # 8. Verify GET /api/tryon/{session_id}/result Endpoint
        response = get_tryon_result(session_id, current_user=created_user, db=db)
        assert isinstance(response, FileResponse), "Expected FileResponse from get_tryon_result"
        assert response.status_code == 200
        assert response.media_type in ("image/webp", "image/jpeg", "image/png")
        assert response.headers.get("Cache-Control") == "private, max-age=3600"
        print(f"[Step 10] Endpoint GET /api/tryon/{session_id}/result returns HTTP 200 FileResponse ({response.media_type})")

        print("\n===================================================================")
        print("  LIVE HUGGING FACE ZEROGPU END-TO-END TEST: 100% SUCCESS (PASS)! ")
        print("===================================================================")

    finally:
        # Cleanup test artifacts
        if customer_photo_name:
            delete_customer_photo(customer_photo_name)
        delete_result_file(session_id)
        s_row = db.get(TryOnSession, session_id)
        if s_row:
            db.delete(s_row)
        if test_product:
            db.delete(test_product)
        if created_user:
            shop_id = created_user.shop_id
            db.delete(created_user)
            if shop_id:
                s = db.get(Shop, shop_id)
                if s:
                    db.delete(s)
        db.commit()
        db.close()


if __name__ == "__main__":
    run_live_zerogpu_e2e()
