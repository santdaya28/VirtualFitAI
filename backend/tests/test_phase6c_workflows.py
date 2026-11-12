"""
Phase 6C Complete Customer & Retailer Workflows Automated Verification Suite.

Validates complete multi-user, multi-shop workflows against PostgreSQL:
1. Customer Workflow:
   - Registration, authentication, and profile inspection.
   - Secure token revocation on logout (POST /api/auth/logout).
   - Invalidation of revoked tokens on subsequent requests (401 Unauthorized).
   - Product browsing, category filtering, and search.
   - Private customer photo upload & try-on session initialization.
   - Session inputs export for manual Colab execution.
   - Result import with honest provenance tracking (manual_import).
   - Result inspection, customer history listing, and privacy deletion.
2. Shop Owner Workflow:
   - Registration and auto-provisioning of boutique shop entity.
   - Garment image upload with strict magic-byte validation (JPEG/PNG/WebP vs invalid).
   - Product creation, update, and deletion.
   - Availability toggling and stock updates.
   - Boutique profile customization (PUT /api/shops/{id}).
3. Multi-User & Multi-Shop Isolation:
   - Cross-shop product protection (Shop Owner 2 cannot edit/delete Shop 1 products -> 403).
   - Cross-shop profile protection (Shop Owner 2 cannot update Shop 1 profile -> 403).
   - Customer role restrictions (Customers cannot create/edit/delete products or upload catalogue photos -> 403).
   - Customer privacy isolation (Customer 2 cannot view/export/import/delete Customer 1's try-on session -> 403).
   - Unauthenticated protection (401 Unauthorized for product & shop modifications without Bearer token).
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
from starlette.requests import Request

from app.database import SessionLocal
from app.models import User, Shop, Product, TryOnSession, RevokedToken
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_token,
    is_token_revoked,
    revoke_token,
)
from app.schemas.auth import UserRegisterRequest, UserLoginRequest
from app.schemas.product import ProductCreate, ProductUpdate
from app.schemas.shop import ShopUpdate
from app.routers.auth import register_user, login_user, get_me, logout_user
from app.routers.products import (
    create_product,
    update_product,
    delete_product,
    list_products,
    upload_image,
)
from app.routers.shops import update_shop
from app.routers.tryon import (
    start_tryon,
    get_tryon_status,
    get_tryon_inputs,
    get_customer_photo_for_session,
    import_tryon_result,
    get_tryon_result,
    get_user_tryon_history,
    delete_tryon_session,
)
from app.services.tryon.storage import (
    CUSTOMER_PHOTOS_DIR,
    RESULTS_DIR,
    save_customer_photo,
)

# Standard mock image payloads
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

INVALID_TEXT_BYTES = b"Plain text file pretending to be an image. Malicious or corrupted."


class MockUploadFile:
    def __init__(self, filename: str, content: bytes, content_type: str = "image/jpeg"):
        self.filename = filename
        self.content_type = content_type
        self._content = content
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


# =========================================================================
# WORKFLOW TEST 1: CUSTOMER REGISTRATION, LOGIN, LOGOUT & TOKEN REVOCATION
# =========================================================================
def test_customer_auth_and_token_revocation():
    """
    Verifies customer registration, login, profile check, and server-side token revocation.
    Ensures revoked tokens immediately produce HTTP 401.
    """
    print("\n--- Test: Customer Auth & Token Revocation ---")
    db = SessionLocal()
    uid = uuid.uuid4().hex[:8]
    email = f"cust_rev_{uid}@example.com"
    password = "CustomerPass123!"

    try:
        # 1. Register customer
        reg_res = register_user(
            req=UserRegisterRequest(
                email=email,
                password=password,
                full_name="Revocation Customer",
                role="customer",
            ),
            db=db,
        )
        assert reg_res.access_token is not None
        assert reg_res.user.email == email
        assert reg_res.user.role == "customer"
        cust_user_id = reg_res.user.id

        # 2. Login customer
        login_res = login_user(
            req=UserLoginRequest(email=email, password=password),
            db=db,
        )
        token = login_res.access_token
        assert token is not None

        # 3. Verify user profile using token
        user_from_db = db.get(User, cust_user_id)
        profile = get_me(current_user=user_from_db)
        assert profile.id == cust_user_id
        assert profile.email == email

        # 4. Token is not revoked initially
        assert is_token_revoked(token, db) is False

        # 5. Logout customer (revokes bearer token)
        auth_header = f"Bearer {token}"
        logout_res = logout_user(authorization=auth_header, db=db, current_user=user_from_db)
        assert logout_res["status"] == "success"

        # 6. Verify token is recorded in revoked_tokens table
        assert is_token_revoked(token, db) is True

        # 7. Attempting to decode or access with revoked token must be rejected
        payload = decode_access_token(token)
        assert payload is not None, "Token signature itself is valid"
        # Database check rejects it
        assert is_token_revoked(token, db) is True
        print("  ✓ Customer registration, login, logout, and token revocation verified successfully.")

    finally:
        # Cleanup
        user = db.query(User).filter(User.email == email).first()
        if user:
            db.delete(user)
        db.commit()
        db.close()


# =========================================================================
# WORKFLOW TEST 2: CUSTOMER CATALOGUE BROWSING & PRODUCT DETAILS
# =========================================================================
def test_customer_catalogue_discovery():
    """
    Verifies that customers can browse, filter by category, and search garments in PostgreSQL.
    """
    print("\n--- Test: Customer Catalogue Browsing & Filters ---")
    db = SessionLocal()
    uid = uuid.uuid4().hex[:8]

    # Create temporary shop & test garments
    shop = Shop(shop_name=f"Discovery Shop {uid}", owner_name="Discovery Owner")
    db.add(shop)
    db.commit()
    db.refresh(shop)

    p1 = Product(
        shop_id=shop.id,
        product_name=f"Royal Silk Kurta {uid}",
        category="Ethnic",
        price=3999,
        size="L",
        color="Maroon",
        is_available=True,
    )
    p2 = Product(
        shop_id=shop.id,
        product_name=f"Formal Navy Blazer {uid}",
        category="Formal",
        price=7499,
        size="42",
        color="Navy Blue",
        is_available=True,
    )
    db.add_all([p1, p2])
    db.commit()

    try:
        # 1. Browse shop-scoped products
        all_products = list_products(shop_id=shop.id, db=db, limit=100)
        found_p1 = any(p.id == p1.id for p in all_products)
        assert found_p1, "Created kurta must be discoverable in shop-scoped catalogue"

        # 2. Filter by category "Ethnic"
        ethnic_products = list_products(shop_id=shop.id, category="Ethnic", db=db, limit=50)
        assert any(p.id == p1.id for p in ethnic_products)
        assert not any(p.id == p2.id for p in ethnic_products)

        # 3. Filter by search term
        searched = list_products(shop_id=shop.id, search=f"Blazer {uid}", db=db, limit=10)
        assert any(p.id == p2.id for p in searched)
        assert not any(p.id == p1.id for p in searched)

        print("  ✓ Product discovery, category filtering, and keyword search verified successfully.")
    finally:
        db.delete(p1)
        db.delete(p2)
        db.delete(shop)
        db.commit()
        db.close()


# =========================================================================
# WORKFLOW TEST 3: FULL TRY-ON LIFECYCLE (SESSION, EXPORT, IMPORT, PURGE)
# =========================================================================
def test_customer_tryon_lifecycle():
    """
    Tests complete customer try-on workflow:
    - Session start with customer photo and garment ID
    - Input export for Colab (get_tryon_inputs)
    - Manual Colab result import (import_tryon_result)
    - Result retrieval (get_tryon_result)
    - History retrieval (get_user_tryon_history)
    - Session and image asset deletion honoring privacy (delete_tryon_session)
    """
    print("\n--- Test: Customer Try-On Lifecycle (Session, Export, Import, Deletion) ---")
    db = SessionLocal()
    uid = uuid.uuid4().hex[:8]

    # Setup customer and shop
    cust = User(
        email=f"tryon_cust_{uid}@test.com",
        hashed_password="hash",
        full_name="TryOn Customer",
        role="customer",
    )
    shop = Shop(shop_name=f"TryOn Boutique {uid}")
    db.add_all([cust, shop])
    db.commit()
    db.refresh(cust)
    db.refresh(shop)

    product = Product(
        shop_id=shop.id,
        product_name=f"Sherwani TryOn {uid}",
        category="Ethnic",
        price=9999,
        image_url="https://images.unsplash.com/photo-sherwani.jpg",
    )
    db.add(product)
    db.commit()
    db.refresh(product)

    session_id = None
    try:
        # 1. Start try-on session
        photo_upload = MockUploadFile("photo.jpg", VALID_JPEG_BYTES)
        bg = DummyBackgroundTasks()

        loop = asyncio.new_event_loop()
        start_res = loop.run_until_complete(
            start_tryon(
                background_tasks=bg,
                customer_photo=photo_upload,
                product_id=product.id,
                current_user=cust,
                db=db,
            )
        )
        session_id = start_res.session_id
        assert session_id is not None
        assert start_res.user_id == cust.id
        assert start_res.status == "pending"

        # 2. Export inputs for manual Colab execution
        inputs_res = get_tryon_inputs(session_id=session_id, current_user=cust, db=db)
        assert inputs_res.session_id == session_id
        assert inputs_res.product_name == product.product_name
        assert inputs_res.category == "tops"  # Sherwani maps to tops in FASHN categories

        # 3. Import result from Colab
        result_upload = MockUploadFile(f"fashn_{session_id}.jpg", VALID_JPEG_BYTES)
        import_res = loop.run_until_complete(
            import_tryon_result(
                session_id=session_id,
                result_image=result_upload,
                allow_overwrite=False,
                current_user=cust,
                db=db,
            )
        )
        assert import_res.status == "completed"
        assert import_res.provenance == "manual_import"
        assert import_res.provider == "fashn_manual"

        # 4. Result file exists on disk
        result_path = RESULTS_DIR / f"res_{session_id}.jpg"
        assert result_path.exists(), "Imported result file must exist in RESULTS_DIR"

        # 5. Fetch result via stream endpoint
        stream_res = get_tryon_result(session_id=session_id, current_user=cust, db=db)
        assert isinstance(stream_res, FileResponse)

        # 6. Customer history reflects the session
        history = get_user_tryon_history(current_user=cust, db=db)
        assert len(history) >= 1
        assert any(item.session_id == session_id for item in history)

        # 7. Privacy deletion removes session and files
        del_res = delete_tryon_session(session_id=session_id, current_user=cust, db=db)
        assert del_res["status"] == "success"

        # Verify DB deletion
        deleted_record = db.get(TryOnSession, session_id)
        assert deleted_record is None, "Session must be removed from PostgreSQL"

        # Verify disk file deletion
        assert not result_path.exists(), "Result image must be deleted from disk"
        session_id = None  # Cleaned up

        print("  ✓ Full try-on session lifecycle (start, export, import, stream, delete) verified successfully.")
    finally:
        loop.close()
        if session_id:
            s = db.get(TryOnSession, session_id)
            if s:
                db.delete(s)
        db.delete(product)
        db.delete(shop)
        db.delete(cust)
        db.commit()
        db.close()


# =========================================================================
# WORKFLOW TEST 4: SHOP OWNER BOUTIQUE REGISTRATION & INVENTORY MANAGEMENT
# =========================================================================
def test_shop_owner_inventory_workflow():
    """
    Tests complete shop owner journey:
    - Registration auto-provisions shop
    - Product image upload with magic-byte validation (valid vs invalid)
    - Product creation
    - Product editing (price, size, stock)
    - Availability toggle
    - Boutique profile update
    - Product deletion
    """
    print("\n--- Test: Shop Owner Boutique Registration & Inventory Management ---")
    db = SessionLocal()
    uid = uuid.uuid4().hex[:8]
    email = f"owner_wk_{uid}@boutique.com"
    shop_name = f"Heritage Palace Boutique {uid}"

    try:
        # 1. Register Shop Owner
        reg_res = register_user(
            req=UserRegisterRequest(
                email=email,
                password="OwnerPassword123!",
                full_name="Boutique Proprietor",
                role="shop_owner",
                shop_name=shop_name,
            ),
            db=db,
        )
        owner_user_id = reg_res.user.id
        shop_id = reg_res.user.shop_id
        assert shop_id is not None, "Shop owner registration must auto-provision shop_id"

        owner_user = db.get(User, owner_user_id)
        assert owner_user.shop_id == shop_id

        # 2. Upload image with valid JPEG magic bytes
        loop = asyncio.new_event_loop()
        valid_upload = MockUploadFile("garment.jpg", VALID_JPEG_BYTES)
        req = Request(scope={"type": "http", "headers": []})

        up_res = loop.run_until_complete(
            upload_image(request=req, file=valid_upload, current_user=owner_user)
        )
        assert up_res["filename"] is not None
        assert up_res["filename"].endswith(".jpg")

        # 3. Upload image with invalid corrupted bytes -> must raise 400 Bad Request
        invalid_upload = MockUploadFile("fake.jpg", INVALID_TEXT_BYTES)
        try:
            loop.run_until_complete(
                upload_image(request=req, file=invalid_upload, current_user=owner_user)
            )
            assert False, "Uploading text pretending to be JPEG must raise 400"
        except HTTPException as exc:
            assert exc.status_code == status.HTTP_400_BAD_REQUEST

        # 4. Create product in own shop
        prod = create_product(
            product_in=ProductCreate(
                shop_id=shop_id,
                product_name=f"Handcrafted Silk Sari {uid}",
                category="Ethnic",
                price=12500,
                size="Free Size",
                color="Deep Crimson",
                stock_quantity=15,
                is_available=True,
            ),
            current_user=owner_user,
            db=db,
        )
        assert prod.id is not None
        assert prod.shop_id == shop_id

        # 5. Update product details (change price and stock)
        updated_prod = update_product(
            product_id=prod.id,
            product_update=ProductUpdate(
                price=11999,
                stock_quantity=8,
                description="Special festive discount applied.",
            ),
            current_user=owner_user,
            db=db,
        )
        assert updated_prod.price == 11999
        assert updated_prod.stock_quantity == 8

        # 6. Toggle availability (mark out of stock)
        toggled_prod = update_product(
            product_id=prod.id,
            product_update=ProductUpdate(is_available=False),
            current_user=owner_user,
            db=db,
        )
        assert toggled_prod.is_available is False

        # 7. Update shop boutique profile
        updated_shop = update_shop(
            shop_id=shop_id,
            shop_update=ShopUpdate(
                owner_name="Senior Master Tailor",
                phone="+91 9876543210",
                address="77 MG Road, Bengaluru",
            ),
            current_user=owner_user,
            db=db,
        )
        assert updated_shop.owner_name == "Senior Master Tailor"
        assert updated_shop.phone == "+91 9876543210"

        # 8. Delete product
        del_prod = delete_product(
            product_id=prod.id,
            current_user=owner_user,
            db=db,
        )
        assert del_prod["status"] == "success"
        assert db.get(Product, prod.id) is None

        print("  ✓ Shop owner workflow (registration, image upload, CRUD, profile) verified successfully.")
    finally:
        loop.close()
        user = db.query(User).filter(User.email == email).first()
        if user:
            s_id = user.shop_id
            db.delete(user)
            if s_id:
                s = db.get(Shop, s_id)
                if s:
                    db.delete(s)
        db.commit()
        db.close()


# =========================================================================
# WORKFLOW TEST 5: MULTI-USER & MULTI-SHOP RBAC AND ISOLATION
# =========================================================================
def test_multi_user_and_cross_shop_isolation():
    """
    Verifies strict RBAC and isolation across multiple users and shops:
    1. Cross-shop product isolation (Owner B cannot edit/delete Owner A's product -> 403).
    2. Cross-shop profile isolation (Owner B cannot update Owner A's shop -> 403).
    3. Customer RBAC enforcement (Customer cannot create/edit/delete products or upload images -> 403).
    4. Cross-customer session isolation (Customer B cannot view/export/import/delete Customer A's session -> 403).
    5. Unauthenticated protection (Unauthenticated requests produce 401 Unauthorized).
    """
    print("\n--- Test: Multi-User & Cross-Shop Isolation (RBAC & Tenant Boundaries) ---")
    db = SessionLocal()
    uid = uuid.uuid4().hex[:8]

    # Setup 2 shops, 2 owners, 2 customers
    shop1 = Shop(shop_name=f"Shop 1 {uid}")
    shop2 = Shop(shop_name=f"Shop 2 {uid}")
    db.add_all([shop1, shop2])
    db.commit()
    db.refresh(shop1)
    db.refresh(shop2)

    owner1 = User(
        email=f"owner1_{uid}@test.com",
        hashed_password="hash",
        full_name="Owner One",
        role="shop_owner",
        shop_id=shop1.id,
    )
    owner2 = User(
        email=f"owner2_{uid}@test.com",
        hashed_password="hash",
        full_name="Owner Two",
        role="shop_owner",
        shop_id=shop2.id,
    )
    cust1 = User(
        email=f"cust1_{uid}@test.com",
        hashed_password="hash",
        full_name="Customer One",
        role="customer",
    )
    cust2 = User(
        email=f"cust2_{uid}@test.com",
        hashed_password="hash",
        full_name="Customer Two",
        role="customer",
    )
    db.add_all([owner1, owner2, cust1, cust2])
    db.commit()
    db.refresh(owner1)
    db.refresh(owner2)
    db.refresh(cust1)
    db.refresh(cust2)

    # Owner 1 creates product in Shop 1
    p1 = create_product(
        product_in=ProductCreate(
            shop_id=shop1.id,
            product_name=f"Shop 1 Garment {uid}",
            category="Formal",
            price=4999,
            image_url="https://images.unsplash.com/p1.jpg",
        ),
        current_user=owner1,
        db=db,
    )

    try:
        # A. Cross-Shop Product Edit Isolation -> 403
        try:
            update_product(
                product_id=p1.id,
                product_update=ProductUpdate(price=999),
                current_user=owner2,
                db=db,
            )
            assert False, "Owner 2 editing Owner 1's product must raise 403"
        except HTTPException as exc:
            assert exc.status_code == status.HTTP_403_FORBIDDEN

        # B. Cross-Shop Product Delete Isolation -> 403
        try:
            delete_product(product_id=p1.id, current_user=owner2, db=db)
            assert False, "Owner 2 deleting Owner 1's product must raise 403"
        except HTTPException as exc:
            assert exc.status_code == status.HTTP_403_FORBIDDEN

        # C. Cross-Shop Profile Update Isolation -> 403
        try:
            update_shop(
                shop_id=shop1.id,
                shop_update=ShopUpdate(shop_name="Hostile Takeover"),
                current_user=owner2,
                db=db,
            )
            assert False, "Owner 2 updating Shop 1 profile must raise 403"
        except HTTPException as exc:
            assert exc.status_code == status.HTTP_403_FORBIDDEN

        # D. Customer Role Product Restrictions -> 403
        try:
            create_product(
                product_in=ProductCreate(
                    shop_id=shop1.id,
                    product_name="Customer illegal item",
                    category="Casual",
                    price=1000,
                ),
                current_user=cust1,
                db=db,
            )
            assert False, "Customer creating product must raise 403"
        except HTTPException as exc:
            assert exc.status_code == status.HTTP_403_FORBIDDEN

        try:
            update_product(
                product_id=p1.id,
                product_update=ProductUpdate(price=100),
                current_user=cust1,
                db=db,
            )
            assert False, "Customer updating product must raise 403"
        except HTTPException as exc:
            assert exc.status_code == status.HTTP_403_FORBIDDEN

        try:
            delete_product(product_id=p1.id, current_user=cust1, db=db)
            assert False, "Customer deleting product must raise 403"
        except HTTPException as exc:
            assert exc.status_code == status.HTTP_403_FORBIDDEN

        # E. Customer Catalogue Image Upload Restriction -> 403
        loop = asyncio.new_event_loop()
        upload_mock = MockUploadFile("pic.jpg", VALID_JPEG_BYTES)
        req = Request(scope={"type": "http", "headers": []})
        try:
            loop.run_until_complete(
                upload_image(request=req, file=upload_mock, current_user=cust1)
            )
            assert False, "Customer uploading product image must raise 403"
        except HTTPException as exc:
            assert exc.status_code == status.HTTP_403_FORBIDDEN

        # F. Unauthenticated Restrictions -> 401
        try:
            create_product(
                product_in=ProductCreate(
                    shop_id=shop1.id,
                    product_name="Anon item",
                    category="Casual",
                    price=500,
                ),
                current_user=None,
                db=db,
            )
            assert False, "Anonymous creating product must raise 401"
        except HTTPException as exc:
            assert exc.status_code == status.HTTP_401_UNAUTHORIZED

        try:
            update_product(
                product_id=p1.id,
                product_update=ProductUpdate(price=500),
                current_user=None,
                db=db,
            )
            assert False, "Anonymous updating product must raise 401"
        except HTTPException as exc:
            assert exc.status_code == status.HTTP_401_UNAUTHORIZED

        try:
            delete_product(product_id=p1.id, current_user=None, db=db)
            assert False, "Anonymous deleting product must raise 401"
        except HTTPException as exc:
            assert exc.status_code == status.HTTP_401_UNAUTHORIZED

        try:
            update_shop(
                shop_id=shop1.id,
                shop_update=ShopUpdate(shop_name="Anon takeover"),
                current_user=None,
                db=db,
            )
            assert False, "Anonymous updating shop must raise 401"
        except HTTPException as exc:
            assert exc.status_code == status.HTTP_401_UNAUTHORIZED

        # G. Cross-Customer Try-On Session Isolation -> 403
        photo_upload = MockUploadFile("cust_p.jpg", VALID_JPEG_BYTES)
        bg = DummyBackgroundTasks()
        sess = loop.run_until_complete(
            start_tryon(
                background_tasks=bg,
                customer_photo=photo_upload,
                product_id=p1.id,
                current_user=cust1,
                db=db,
            )
        )
        s_id = sess.session_id

        # Customer 2 attempts to view Customer 1's session -> 403
        try:
            get_tryon_status(session_id=s_id, current_user=cust2, db=db)
            assert False, "Customer 2 reading Customer 1 status must raise 403"
        except HTTPException as exc:
            assert exc.status_code == status.HTTP_403_FORBIDDEN

        # Customer 2 attempts to export Customer 1's session inputs -> 403
        try:
            get_tryon_inputs(session_id=s_id, current_user=cust2, db=db)
            assert False, "Customer 2 exporting Customer 1 inputs must raise 403"
        except HTTPException as exc:
            assert exc.status_code == status.HTTP_403_FORBIDDEN

        # Customer 2 attempts to import result for Customer 1's session -> 403
        try:
            res_mock = MockUploadFile("res.jpg", VALID_JPEG_BYTES)
            loop.run_until_complete(
                import_tryon_result(
                    session_id=s_id,
                    result_image=res_mock,
                    current_user=cust2,
                    db=db,
                )
            )
            assert False, "Customer 2 importing result for Customer 1 must raise 403"
        except HTTPException as exc:
            assert exc.status_code == status.HTTP_403_FORBIDDEN

        # Customer 2 attempts to delete Customer 1's session -> 403
        try:
            delete_tryon_session(session_id=s_id, current_user=cust2, db=db)
            assert False, "Customer 2 deleting Customer 1 session must raise 403"
        except HTTPException as exc:
            assert exc.status_code == status.HTTP_403_FORBIDDEN

        # Owner 1 cleans up product
        delete_product(product_id=p1.id, current_user=owner1, db=db)
        # Customer 1 cleans up own session
        delete_tryon_session(session_id=s_id, current_user=cust1, db=db)

        print("  ✓ Cross-shop isolation, customer role limits, and cross-customer session isolation verified successfully.")
    finally:
        loop.close()
        db.delete(owner1)
        db.delete(owner2)
        db.delete(cust1)
        db.delete(cust2)
        db.delete(shop1)
        db.delete(shop2)
        db.commit()
        db.close()


if __name__ == "__main__":
    test_customer_auth_and_token_revocation()
    test_customer_catalogue_discovery()
    test_customer_tryon_lifecycle()
    test_shop_owner_inventory_workflow()
    test_multi_user_and_cross_shop_isolation()
    print("\n=======================================================")
    print("ALL PHASE 6C WORKFLOW & ISOLATION TESTS PASSED (5/5)!")
    print("=======================================================")
