"""
Standalone automated verification script for VirtualFit AI Shop & Product CRUD APIs.
Tests Pydantic models, routing, database interactions, validation rules, and error handling.
"""
import sys
from decimal import Decimal
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi import HTTPException

from app.database import Base
from app.models import Shop, Product
from app.routers.shops import (
    create_shop,
    list_shops,
    get_shop,
    update_shop,
    delete_shop,
)
from app.routers.products import (
    create_product,
    list_products,
    get_product,
    update_product,
    delete_product,
)
from app.schemas.shop import ShopCreate, ShopUpdate
from app.schemas.product import ProductCreate, ProductUpdate
from app.main import app


def test_crud_suite():
    print("=" * 60)
    print(" VirtualFit AI — Shop & Product CRUD API Verification Suite")
    print("=" * 60)

    # In-memory SQLite isolated testing session
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSession()

    # -------------------------------------------------------------
    # 1. OpenAPI Route Registration
    # -------------------------------------------------------------
    openapi = app.openapi()
    expected_paths = [
        "/api/shops",
        "/api/shops/{shop_id}",
        "/api/products",
        "/api/products/{product_id}",
    ]
    for path in expected_paths:
        assert path in openapi["paths"], f"Missing OpenAPI path: {path}"
    print("✓ OpenAPI paths verified for /api/shops and /api/products")

    # -------------------------------------------------------------
    # 2. Shop CRUD
    # -------------------------------------------------------------
    # POST /api/shops
    shop_data = ShopCreate(
        shop_name="Emerald Elegance Couture",
        owner_name="Vikram Sethi",
        email="contact@emeraldeyg.com",
        phone="+91 98200 11223",
        address="45 Heritage Boulevard, Mumbai, MH",
    )
    shop = create_shop(shop_data, db)
    assert shop.id == 1
    assert shop.shop_name == "Emerald Elegance Couture"
    print(f"✓ POST /api/shops: Created shop ID {shop.id} ('{shop.shop_name}')")

    # GET /api/shops/{shop_id}
    fetched_shop = get_shop(shop.id, db)
    assert fetched_shop.shop_name == "Emerald Elegance Couture"
    print(f"✓ GET /api/shops/{shop.id}: Successfully fetched shop")

    # GET /api/shops (list & search)
    shops = list_shops(skip=0, limit=10, search="Emerald", db=db)
    assert len(shops) == 1
    print(f"✓ GET /api/shops: Search and pagination returned {len(shops)} shop(s)")

    # PUT /api/shops/{shop_id}
    update_data = ShopUpdate(phone="+91 98200 99999", owner_name="Vikram R. Sethi")
    updated_shop = update_shop(shop.id, update_data, db)
    assert updated_shop.phone == "+91 98200 99999"
    assert updated_shop.owner_name == "Vikram R. Sethi"
    print(f"✓ PUT /api/shops/{shop.id}: Updated shop details")

    # -------------------------------------------------------------
    # 3. Product CRUD & Foreign Key Validation
    # -------------------------------------------------------------
    # POST /api/products with non-existent shop -> 400 Bad Request
    invalid_product_data = ProductCreate(
        shop_id=9999,
        product_name="Phantom Suit",
        category="Formal",
        price=Decimal("4999.00"),
    )
    try:
        create_product(invalid_product_data, db)
        assert False, "Should have rejected product with non-existent shop_id"
    except HTTPException as exc:
        assert exc.status_code == 400
        assert "Shop with ID 9999 does not exist" in exc.detail
        print("✓ POST /api/products: Correctly rejected invalid shop_id with 400 Bad Request")

    # POST /api/products (valid)
    product_data_1 = ProductCreate(
        shop_id=shop.id,
        product_name="Royal Bandhgala Suit",
        description="Handcrafted pure wool structured Bandhgala with antique brass buttons.",
        category="Ethnic",
        price=Decimal("12500.00"),
        size="38, 40, 42, 44",
        color="Royal Navy",
        image_url="https://images.unsplash.com/photo-1594938298603-c8148c4dae35",
        stock_quantity=8,
        is_available=True,
    )
    prod_1 = create_product(product_data_1, db)
    assert prod_1.id == 1
    assert prod_1.shop_id == shop.id
    assert prod_1.price == Decimal("12500.00")
    print(f"✓ POST /api/products: Created product ID {prod_1.id} ('{prod_1.product_name}')")

    product_data_2 = ProductCreate(
        shop_id=shop.id,
        product_name="Tailored Oxford Cotton Shirt",
        description="Crisp 100% Egyptian cotton formal shirt.",
        category="Formal",
        price=Decimal("2800.00"),
        size="S, M, L, XL",
        color="Classic White",
        stock_quantity=30,
        is_available=True,
    )
    prod_2 = create_product(product_data_2, db)
    assert prod_2.id == 2
    print(f"✓ POST /api/products: Created second product ID {prod_2.id} ('{prod_2.product_name}')")

    # GET /api/products (filters)
    all_products = list_products(db=db)
    assert len(all_products) == 2
    formal_products = list_products(category="Formal", db=db)
    assert len(formal_products) == 1
    assert formal_products[0].product_name == "Tailored Oxford Cotton Shirt"
    search_products = list_products(search="Bandhgala", db=db)
    assert len(search_products) == 1
    assert search_products[0].product_name == "Royal Bandhgala Suit"
    print("✓ GET /api/products: Filtering by category and search term succeeded")

    # GET /api/products/{product_id}
    fetched_prod = get_product(prod_1.id, db)
    assert fetched_prod.product_name == "Royal Bandhgala Suit"
    print(f"✓ GET /api/products/{prod_1.id}: Fetched product details")

    # PUT /api/products/{product_id}
    prod_update = ProductUpdate(price=Decimal("11900.00"), stock_quantity=5)
    updated_prod = update_product(prod_1.id, prod_update, db)
    assert updated_prod.price == Decimal("11900.00")
    assert updated_prod.stock_quantity == 5
    print(f"✓ PUT /api/products/{prod_1.id}: Updated product price and stock")

    # DELETE /api/products/{product_id}
    del_res = delete_product(prod_2.id, db)
    assert del_res["status"] == "success"
    assert del_res["deleted_id"] == prod_2.id
    try:
        get_product(prod_2.id, db)
        assert False, "Should have raised 404 for deleted product"
    except HTTPException as exc:
        assert exc.status_code == 404
    print(f"✓ DELETE /api/products/{prod_2.id}: Successfully deleted product and verified 404")

    # DELETE /api/shops/{shop_id} (cascades to remaining products)
    del_shop_res = delete_shop(shop.id, db)
    assert del_shop_res["status"] == "success"
    try:
        get_shop(shop.id, db)
        assert False, "Should have raised 404 for deleted shop"
    except HTTPException as exc:
        assert exc.status_code == 404
    assert len(list_products(db=db)) == 0
    print(f"✓ DELETE /api/shops/{shop.id}: Cascading deletion removed shop and all child products")

    print("=" * 60)
    print(" ALL 12 SHOP & PRODUCT CRUD VERIFICATION CHECKS PASSED!")
    print("=" * 60)


if __name__ == "__main__":
    test_crud_suite()

