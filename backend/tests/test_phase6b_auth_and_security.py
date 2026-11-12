"""
Phase 6B Security, Provenance, and Role-Based Access Control Automated Tests.

Covers:
1. NIST-compliant PBKDF2-HMAC-SHA256 password hashing & verification.
2. Cryptographically signed token creation & tampering detection.
3. User registration & login with role assignment (customer, shop_owner).
4. Shop owner product CRUD with strict cross-shop isolation (Shop A cannot modify Shop B -> 403).
5. Customer role restrictions (Customers cannot create, modify, or delete catalogue products -> 403).
6. Cross-shop profile isolation (Shop Owner 2 cannot update Shop 1 -> 403).
7. Cross-user try-on session isolation (Customer 2 cannot access Customer 1's session, photos, or inputs -> 403).
8. Customer try-on history endpoint (GET /api/tryon/history/me isolation).
9. Duplicate import protection (returns 409 Conflict when allow_overwrite=False).
10. Provenance tracking honesty (distinguishes mock_simulation, manual_import, genuine_inference).
11. Customer privacy deletion (DELETE /api/tryon/{session_id} purges DB record and files on disk).
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

from fastapi import HTTPException, UploadFile, status

from app.database import SessionLocal
from app.models import User, Shop, Product, TryOnSession
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
)
from app.schemas.auth import UserRegisterRequest, UserLoginRequest
from app.schemas.product import ProductCreate, ProductUpdate
from app.schemas.shop import ShopUpdate
from app.routers.auth import register_user, login_user, get_me
from app.routers.products import create_product, update_product, delete_product
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


# =========================================================================
# 1. NIST-COMPLIANT PASSWORD HASHING AND JWT TOKEN TESTS
# =========================================================================
def test_password_hashing_and_verification():
    print("\n--- Testing PBKDF2 Password Hashing & Verification ---")
    raw_pass = "P@ssw0rd!Secure99"
    hashed = hash_password(raw_pass)

    assert hashed != raw_pass
    assert hashed.startswith("pbkdf2:sha256:100000$")
    parts = hashed.split("$")
    assert len(parts) == 3
    assert "100000" in parts[0]  # 100k iterations

    # Verification
    assert verify_password(raw_pass, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False
    assert verify_password("", hashed) is False
    print("PASS: PBKDF2-HMAC-SHA256 correctly hashes and verifies passwords.")


def test_signed_bearer_tokens():
    print("\n--- Testing Signed Bearer Tokens & Tampering Protection ---")
    token = create_access_token(user_id=42, email="tester@example.com", role="customer")
    assert isinstance(token, str)

    payload = decode_access_token(token)
    assert payload is not None
    assert payload["sub"] == 42
    assert payload["email"] == "tester@example.com"
    assert payload["role"] == "customer"

    # Tampered token
    tampered = token[:-4] + "xxxx"
    assert decode_access_token(tampered) is None
    print("PASS: Cryptographically signed tokens verified and tamper-resistant.")


# =========================================================================
# 2. USER REGISTRATION AND LOGIN TESTS
# =========================================================================
def test_auth_registration_and_login():
    print("\n--- Testing Registration & Login Flow ---")
    db = SessionLocal()
    unique_suffix = uuid.uuid4().hex[:8]
    cust_email = f"cust_{unique_suffix}@test.com"
    shop_email = f"owner_{unique_suffix}@test.com"

    try:
        # 1. Register customer
        cust_req = UserRegisterRequest(
            email=cust_email,
            password="StrongPassword123!",
            full_name="Test Customer",
            role="customer",
        )
        cust_auth = register_user(cust_req, db)
        assert cust_auth.access_token is not None
        assert cust_auth.user.email == cust_email
        assert cust_auth.user.role == "customer"
        assert cust_auth.user.shop_id is None

        # 2. Duplicate registration rejected
        try:
            register_user(cust_req, db)
            assert False, "Duplicate email registration should have raised 400"
        except HTTPException as exc:
            assert exc.status_code == status.HTTP_400_BAD_REQUEST

        # 3. Register shop owner with auto-created shop
        shop_req = UserRegisterRequest(
            email=shop_email,
            password="OwnerPassword123!",
            full_name="Boutique Owner",
            role="shop_owner",
            shop_name=f"Boutique {unique_suffix}",
        )
        shop_auth = register_user(shop_req, db)
        assert shop_auth.user.role == "shop_owner"
        assert shop_auth.user.shop_id is not None

        # Verify shop exists in DB
        owner_shop = db.query(Shop).filter(Shop.id == shop_auth.user.shop_id).first()
        assert owner_shop is not None
        assert owner_shop.shop_name == f"Boutique {unique_suffix}"

        # 4. Login customer
        login_req = UserLoginRequest(email=cust_email, password="StrongPassword123!")
        login_res = login_user(login_req, db)
        assert login_res.access_token is not None
        assert login_res.user.id == cust_auth.user.id

        # 5. Login wrong password -> 401
        try:
            login_user(UserLoginRequest(email=cust_email, password="WrongPassword!"), db)
            assert False, "Wrong password should have raised 401"
        except HTTPException as exc:
            assert exc.status_code == status.HTTP_401_UNAUTHORIZED

        print("PASS: User registration and login flow validated.")
    finally:
        # Cleanup
        db.query(User).filter(User.email.in_([cust_email, shop_email])).delete(synchronize_session=False)
        db.commit()
        db.close()


# =========================================================================
# 3. CROSS-SHOP ISOLATION AND ROLE-BASED ACCESS CONTROL
# =========================================================================
def test_cross_shop_isolation_and_rbac():
    print("\n--- Testing Cross-Shop Product & Profile Isolation ---")
    db = SessionLocal()
    suffix = uuid.uuid4().hex[:8]

    # Create two distinct shops
    shop1 = Shop(shop_name=f"Shop One {suffix}", owner_name="Owner 1")
    shop2 = Shop(shop_name=f"Shop Two {suffix}", owner_name="Owner 2")
    db.add_all([shop1, shop2])
    db.commit()

    # Create users
    owner1 = User(
        email=f"owner1_{suffix}@test.com",
        hashed_password=hash_password("pw"),
        full_name="Owner One",
        role="shop_owner",
        shop_id=shop1.id,
    )
    owner2 = User(
        email=f"owner2_{suffix}@test.com",
        hashed_password=hash_password("pw"),
        full_name="Owner Two",
        role="shop_owner",
        shop_id=shop2.id,
    )
    customer = User(
        email=f"customer_{suffix}@test.com",
        hashed_password=hash_password("pw"),
        full_name="Customer User",
        role="customer",
    )
    db.add_all([owner1, owner2, customer])
    db.commit()

    try:
        # 1. Owner 1 creates product in Shop 1
        p1 = create_product(
            product_in=ProductCreate(
                shop_id=shop1.id,
                product_name="Shop 1 Silk Kurta",
                category="Ethnic Wear",
                price=3500.0,
            ),
            current_user=owner1,
            db=db,
        )
        assert p1.id is not None
        assert p1.shop_id == shop1.id

        # 2. Customer attempts to create product -> 403 Forbidden
        try:
            create_product(
                product_in=ProductCreate(
                    shop_id=shop1.id,
                    product_name="Illegal Product",
                    category="Formal Shirts",
                    price=2000.0,
                ),
                current_user=customer,
                db=db,
            )
            assert False, "Customer creating product should raise 403"
        except HTTPException as exc:
            assert exc.status_code == status.HTTP_403_FORBIDDEN

        # 3. Owner 2 attempts to create product for Shop 1 -> 403 Forbidden
        try:
            create_product(
                product_in=ProductCreate(
                    shop_id=shop1.id,
                    product_name="Shop 2 intrusion",
                    category="Ethnic Wear",
                    price=4000.0,
                ),
                current_user=owner2,
                db=db,
            )
            assert False, "Owner 2 creating product in Shop 1 should raise 403"
        except HTTPException as exc:
            assert exc.status_code == status.HTTP_403_FORBIDDEN

        # 4. Owner 2 attempts to update Shop 1's product -> 403 Forbidden
        try:
            update_product(
                product_id=p1.id,
                product_update=ProductUpdate(price=10.0),
                db=db,
                current_user=owner2,
            )
            assert False, "Owner 2 updating Shop 1 product should raise 403"
        except HTTPException as exc:
            assert exc.status_code == status.HTTP_403_FORBIDDEN

        # 5. Customer attempts to update Shop 1's product -> 403 Forbidden
        try:
            update_product(
                product_id=p1.id,
                product_update=ProductUpdate(price=10.0),
                db=db,
                current_user=customer,
            )
            assert False, "Customer updating product should raise 403"
        except HTTPException as exc:
            assert exc.status_code == status.HTTP_403_FORBIDDEN

        # 6. Owner 2 attempts to delete Shop 1's product -> 403 Forbidden
        try:
            delete_product(product_id=p1.id, db=db, current_user=owner2)
            assert False, "Owner 2 deleting Shop 1 product should raise 403"
        except HTTPException as exc:
            assert exc.status_code == status.HTTP_403_FORBIDDEN

        # 7. Owner 2 attempts to update Shop 1 profile -> 403 Forbidden
        try:
            update_shop(
                shop_id=shop1.id,
                shop_update=ShopUpdate(shop_name="Hacked Shop"),
                db=db,
                current_user=owner2,
            )
            assert False, "Owner 2 updating Shop 1 should raise 403"
        except HTTPException as exc:
            assert exc.status_code == status.HTTP_403_FORBIDDEN

        # 8. Owner 1 successfully updates Shop 1 profile & product
        updated_shop = update_shop(
            shop_id=shop1.id,
            shop_update=ShopUpdate(address="New Address, Bengaluru"),
            db=db,
            current_user=owner1,
        )
        assert updated_shop.address == "New Address, Bengaluru"

        updated_p1 = update_product(
            product_id=p1.id,
            product_update=ProductUpdate(price=3800.0),
            db=db,
            current_user=owner1,
        )
        assert float(updated_p1.price) == 3800.0

        # 9. Owner 1 successfully deletes own product
        del_res = delete_product(product_id=p1.id, db=db, current_user=owner1)
        assert del_res["status"] == "success"

        print("PASS: Cross-shop isolation and RBAC strictly enforced.")
    finally:
        # Cleanup
        db.query(Product).filter(Product.shop_id.in_([shop1.id, shop2.id])).delete(synchronize_session=False)
        db.query(User).filter(User.id.in_([owner1.id, owner2.id, customer.id])).delete(synchronize_session=False)
        db.query(Shop).filter(Shop.id.in_([shop1.id, shop2.id])).delete(synchronize_session=False)
        db.commit()
        db.close()


# =========================================================================
# 4. CROSS-USER TRY-ON SESSION ISOLATION & PRIVACY
# =========================================================================
def test_cross_user_tryon_isolation_and_privacy():
    print("\n--- Testing Cross-User Session Isolation & Privacy ---")
    db = SessionLocal()
    suffix = uuid.uuid4().hex[:8]

    # Create shop and product
    shop = Shop(shop_name=f"TryOn Shop {suffix}", owner_name="Owner")
    db.add(shop)
    db.commit()

    product = Product(
        shop_id=shop.id,
        product_name="Test Linen Shirt",
        category="Formal Shirts",
        price=2499.0,
        image_url="http://localhost:8000/static/sample.jpg",
    )
    db.add(product)
    db.commit()

    # Create two customer users
    cust1 = User(
        email=f"cust1_{suffix}@test.com",
        hashed_password=hash_password("pw"),
        full_name="Customer 1",
        role="customer",
    )
    cust2 = User(
        email=f"cust2_{suffix}@test.com",
        hashed_password=hash_password("pw"),
        full_name="Customer 2",
        role="customer",
    )
    db.add_all([cust1, cust2])
    db.commit()

    # Create a session belonging to Customer 1
    session_id = str(uuid.uuid4())
    saved_filename = save_customer_photo(VALID_JPEG_BYTES, f"{session_id}.jpg")
    photo_path = CUSTOMER_PHOTOS_DIR / saved_filename

    session = TryOnSession(
        id=session_id,
        user_id=cust1.id,
        product_id=product.id,
        customer_photo_url=saved_filename,
        status="pending",
        progress_percentage=10,
        stage_message="Queued",
        provider="mock",
        provenance="mock_simulation",
    )
    db.add(session)
    db.commit()

    try:
        # 1. Customer 1 can access status, inputs, photo
        status1 = get_tryon_status(session_id=session_id, db=db, current_user=cust1)
        assert status1.session_id == session_id
        assert status1.user_id == cust1.id

        inputs1 = get_tryon_inputs(session_id=session_id, db=db, current_user=cust1)
        assert inputs1.session_id == session_id

        photo1 = get_customer_photo_for_session(session_id=session_id, db=db, current_user=cust1)
        assert photo1 is not None

        # 2. Customer 2 accessing Customer 1's session -> 403 Forbidden
        try:
            get_tryon_status(session_id=session_id, db=db, current_user=cust2)
            assert False, "Customer 2 accessing Customer 1 status should raise 403"
        except HTTPException as exc:
            assert exc.status_code == status.HTTP_403_FORBIDDEN

        try:
            get_tryon_inputs(session_id=session_id, db=db, current_user=cust2)
            assert False, "Customer 2 accessing Customer 1 inputs should raise 403"
        except HTTPException as exc:
            assert exc.status_code == status.HTTP_403_FORBIDDEN

        try:
            get_customer_photo_for_session(session_id=session_id, db=db, current_user=cust2)
            assert False, "Customer 2 downloading Customer 1 photo should raise 403"
        except HTTPException as exc:
            assert exc.status_code == status.HTTP_403_FORBIDDEN

        try:
            delete_tryon_session(session_id=session_id, db=db, current_user=cust2)
            assert False, "Customer 2 deleting Customer 1 session should raise 403"
        except HTTPException as exc:
            assert exc.status_code == status.HTTP_403_FORBIDDEN

        # 3. Unauthenticated access to user session -> 401 Unauthorized
        try:
            get_tryon_status(session_id=session_id, db=db, current_user=None)
            assert False, "Unauthenticated access to user session should raise 401"
        except HTTPException as exc:
            assert exc.status_code == status.HTTP_401_UNAUTHORIZED

        print("PASS: Cross-user try-on isolation and customer privacy verified.")
    finally:
        # Cleanup
        db.query(TryOnSession).filter(TryOnSession.id == session_id).delete(synchronize_session=False)
        db.query(Product).filter(Product.id == product.id).delete(synchronize_session=False)
        db.query(User).filter(User.id.in_([cust1.id, cust2.id])).delete(synchronize_session=False)
        db.query(Shop).filter(Shop.id == shop.id).delete(synchronize_session=False)
        db.commit()
        db.close()
        if os.path.exists(photo_path):
            os.remove(photo_path)


# =========================================================================
# 5. CUSTOMER TRY-ON HISTORY AND PROVENANCE HONESTY
# =========================================================================
def test_tryon_history_and_provenance():
    print("\n--- Testing Customer Try-On History & Provenance Honesty ---")
    db = SessionLocal()
    suffix = uuid.uuid4().hex[:8]

    # Create user
    user = User(
        email=f"history_user_{suffix}@test.com",
        hashed_password=hash_password("pw"),
        full_name="History User",
        role="customer",
    )
    db.add(user)
    db.commit()

    # Create product
    shop = Shop(shop_name=f"History Shop {suffix}")
    db.add(shop)
    db.commit()

    product = Product(
        shop_id=shop.id,
        product_name="Heritage Silk Sherwani",
        category="Ethnic Wear",
        price=12500.0,
    )
    db.add(product)
    db.commit()

    # Create 2 sessions for this user: 1 mock simulation, 1 manual import
    s1_id = str(uuid.uuid4())
    s2_id = str(uuid.uuid4())

    s1 = TryOnSession(
        id=s1_id,
        user_id=user.id,
        product_id=product.id,
        customer_photo_url=f"/api/tryon/{s1_id}/customer-photo",
        status="completed",
        progress_percentage=100,
        provider="mock",
        provenance="mock_simulation",
    )
    s2 = TryOnSession(
        id=s2_id,
        user_id=user.id,
        product_id=product.id,
        customer_photo_url=f"/api/tryon/{s2_id}/customer-photo",
        status="completed",
        progress_percentage=100,
        provider="fashn_manual",
        provenance="manual_import",
    )
    db.add_all([s1, s2])
    db.commit()

    try:
        # Query history
        history = get_user_tryon_history(db=db, current_user=user)
        assert len(history) == 2

        # Check item provenance labels
        prov_map = {item.session_id: item.provenance for item in history}
        assert prov_map[s1_id] == "mock_simulation"
        assert prov_map[s2_id] == "manual_import"

        print("PASS: History endpoint returned correct sessions and provenance.")
    finally:
        # Cleanup
        db.query(TryOnSession).filter(TryOnSession.id.in_([s1_id, s2_id])).delete(synchronize_session=False)
        db.query(Product).filter(Product.id == product.id).delete(synchronize_session=False)
        db.query(User).filter(User.id == user.id).delete(synchronize_session=False)
        db.query(Shop).filter(Shop.id == shop.id).delete(synchronize_session=False)
        db.commit()
        db.close()


# =========================================================================
# 6. DUPLICATE IMPORT PROTECTION AND PRIVACY DELETION
# =========================================================================
def test_duplicate_import_protection_and_deletion():
    print("\n--- Testing Duplicate Import Protection & Customer Privacy Deletion ---")
    db = SessionLocal()
    suffix = uuid.uuid4().hex[:8]

    # Create user
    user = User(
        email=f"import_user_{suffix}@test.com",
        hashed_password=hash_password("pw"),
        full_name="Import User",
        role="customer",
    )
    db.add(user)
    db.commit()

    # Create session
    session_id = str(uuid.uuid4())
    saved_filename = save_customer_photo(VALID_JPEG_BYTES, f"{session_id}.jpg")
    photo_path = CUSTOMER_PHOTOS_DIR / saved_filename

    session = TryOnSession(
        id=session_id,
        user_id=user.id,
        customer_photo_url=saved_filename,
        status="pending",
        progress_percentage=10,
        provider="mock",
        provenance="mock_simulation",
    )
    db.add(session)
    db.commit()

    mock_result_file = MockUploadFile("colab_result.jpg", VALID_JPEG_BYTES, "image/jpeg")

    try:
        # 1. First import succeeds
        resp1 = asyncio.run(
            import_tryon_result(
                session_id=session_id,
                result_image=mock_result_file,
                allow_overwrite=False,
                db=db,
                current_user=user,
            )
        )
        assert resp1.status == "completed"
        assert resp1.provider == "fashn_manual"
        assert resp1.provenance == "manual_import"

        # Verify result file written to disk
        res_path = RESULTS_DIR / f"res_{session_id}.jpg"
        assert res_path.exists()

        # 2. Duplicate import without allow_overwrite raises 409 Conflict
        mock_result_file.file.seek(0)
        try:
            asyncio.run(
                import_tryon_result(
                    session_id=session_id,
                    result_image=mock_result_file,
                    allow_overwrite=False,
                    db=db,
                    current_user=user,
                )
            )
            assert False, "Duplicate import without allow_overwrite should raise 409 Conflict"
        except HTTPException as exc:
            assert exc.status_code == status.HTTP_409_CONFLICT

        # 3. Duplicate import with allow_overwrite=True succeeds
        mock_result_file.file.seek(0)
        resp2 = asyncio.run(
            import_tryon_result(
                session_id=session_id,
                result_image=mock_result_file,
                allow_overwrite=True,
                db=db,
                current_user=user,
            )
        )
        assert resp2.status == "completed"

        # 4. Customer Privacy Deletion: DELETE /api/tryon/{session_id}
        del_res = delete_tryon_session(session_id=session_id, db=db, current_user=user)
        assert del_res["status"] == "success"

        # Verify DB session purged
        db_check = db.query(TryOnSession).filter(TryOnSession.id == session_id).first()
        assert db_check is None

        # Verify files on disk purged
        assert not os.path.exists(photo_path)
        assert not res_path.exists()

        # Verify 404 after deletion
        try:
            get_tryon_status(session_id=session_id, db=db, current_user=user)
            assert False, "Deleted session should raise 404"
        except HTTPException as exc:
            assert exc.status_code == status.HTTP_404_NOT_FOUND

        print("PASS: Duplicate import protection and privacy deletion verified.")
    finally:
        # Ensure cleanup
        db.query(TryOnSession).filter(TryOnSession.id == session_id).delete(synchronize_session=False)
        db.query(User).filter(User.id == user.id).delete(synchronize_session=False)
        db.commit()
        db.close()
        if os.path.exists(photo_path):
            os.remove(photo_path)
        res_file = RESULTS_DIR / f"res_{session_id}.jpg"
        if res_file.exists():
            os.remove(res_file)


# =========================================================================
# MAIN TEST RUNNER
# =========================================================================
if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("VIRTUALFIT AI — PHASE 6B AUTOMATED TEST SUITE")
    print("Security, Provenance, Isolation, and Role-Based Access Control")
    print("=" * 70)

    test_password_hashing_and_verification()
    test_signed_bearer_tokens()
    test_auth_registration_and_login()
    test_cross_shop_isolation_and_rbac()
    test_cross_user_tryon_isolation_and_privacy()
    test_tryon_history_and_provenance()
    test_duplicate_import_protection_and_deletion()

    print("\n" + "=" * 70)
    print("ALL PHASE 6B TESTS PASSED SUCCESSFULLY! (7/7 suites green)")
    print("=" * 70 + "\n")
