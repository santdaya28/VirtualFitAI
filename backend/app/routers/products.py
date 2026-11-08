import logging
from typing import List, Optional, Annotated
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database import get_db
from app.models import Shop, Product
from app.schemas.product import (
    ProductCreate,
    ProductUpdate,
    ProductResponse,
)

logger = logging.getLogger("virtualfit.products")

router = APIRouter(prefix="/api/products", tags=["Products"])


def get_db_session(db: Optional[Session] = Depends(get_db)) -> Session:
    """
    Dependency ensuring active database session is available.
    Returns 503 if database connection is offline.
    """
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection is not available. Please verify PostgreSQL service is running.",
        )
    return db


@router.post(
    "",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new garment product",
    description="Adds a new garment item to the catalogue associated with a registered shop.",
)
def create_product(
    product_in: ProductCreate,
    db: Session = Depends(get_db_session),
):
    """
    Creates a new Product.
    Validates that the referenced shop_id exists in the database.
    """
    # 1. Validate that the parent Shop exists
    parent_shop = db.get(Shop, product_in.shop_id)
    if not parent_shop:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot create product: Shop with ID {product_in.shop_id} does not exist.",
        )

    # 2. Validate product name
    clean_name = product_in.product_name.strip()
    if not clean_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Product name cannot be empty or whitespace.",
        )

    try:
        new_product = Product(
            shop_id=product_in.shop_id,
            product_name=clean_name,
            description=product_in.description.strip() if product_in.description else None,
            category=product_in.category.strip() if product_in.category else None,
            price=product_in.price,
            size=product_in.size.strip() if product_in.size else None,
            color=product_in.color.strip() if product_in.color else None,
            image_url=product_in.image_url.strip() if product_in.image_url else None,
            stock_quantity=product_in.stock_quantity,
            is_available=product_in.is_available,
        )
        db.add(new_product)
        db.commit()
        db.refresh(new_product)
        logger.info(
            f"Created new product ID {new_product.id}: '{new_product.product_name}' for shop ID {new_product.shop_id}"
        )
        return new_product
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        logger.error(f"Error creating product: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error occurred while creating the product.",
        )


@router.get(
    "",
    response_model=List[ProductResponse],
    summary="List garment products",
    description="Retrieves a list of products with optional filters by shop_id, category, search term, and pagination.",
)
def list_products(
    shop_id: Annotated[Optional[int], Query(description="Filter products belonging to a specific shop ID")] = None,
    category: Annotated[Optional[str], Query(description="Filter products by category (case-insensitive substring)")] = None,
    search: Annotated[Optional[str], Query(description="Search by product name or description (case-insensitive)")] = None,
    skip: Annotated[int, Query(ge=0, description="Number of records to skip for pagination")] = 0,
    limit: Annotated[int, Query(ge=1, le=100, description="Maximum number of records to return per page")] = 20,
    db: Session = Depends(get_db_session),
):
    """
    Lists products with optional filtering by shop_id, category, and search query.
    """
    stmt = select(Product)

    if shop_id is not None:
        stmt = stmt.where(Product.shop_id == shop_id)

    if category and category.strip():
        clean_cat = f"%{category.strip()}%"
        stmt = stmt.where(Product.category.ilike(clean_cat))

    if search and search.strip():
        term = f"%{search.strip()}%"
        stmt = stmt.where(
            Product.product_name.ilike(term) | Product.description.ilike(term)
        )

    stmt = stmt.order_by(Product.id.desc()).offset(skip).limit(limit)
    products = db.scalars(stmt).all()
    return products


@router.get(
    "/{product_id}",
    response_model=ProductResponse,
    summary="Get product by ID",
    description="Retrieves detailed information for a specific product by its ID.",
)
def get_product(
    product_id: int,
    db: Session = Depends(get_db_session),
):
    """
    Returns a single product by primary key ID. Returns 404 if not found.
    """
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID {product_id} not found.",
        )
    return product


@router.put(
    "/{product_id}",
    response_model=ProductResponse,
    summary="Update product details",
    description="Updates fields of an existing product. Validates shop_id if changed.",
)
def update_product(
    product_id: int,
    product_update: ProductUpdate,
    db: Session = Depends(get_db_session),
):
    """
    Updates editable fields of a product.
    Returns 404 if product does not exist.
    Returns 400 if target shop_id does not exist.
    """
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID {product_id} not found.",
        )

    update_data = product_update.model_dump(exclude_unset=True)
    if not update_data:
        return product

    # If updating shop_id, verify the target shop exists
    if "shop_id" in update_data and update_data["shop_id"] is not None:
        target_shop_id = update_data["shop_id"]
        if target_shop_id != product.shop_id:
            target_shop = db.get(Shop, target_shop_id)
            if not target_shop:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot update product: Target Shop with ID {target_shop_id} does not exist.",
                )
            product.shop_id = target_shop_id

    if "product_name" in update_data:
        val = update_data["product_name"]
        if val is not None:
            clean_name = val.strip()
            if not clean_name:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Product name cannot be empty or whitespace.",
                )
            product.product_name = clean_name

    if "description" in update_data:
        product.description = update_data["description"].strip() if update_data["description"] else None
    if "category" in update_data:
        product.category = update_data["category"].strip() if update_data["category"] else None
    if "price" in update_data and update_data["price"] is not None:
        product.price = update_data["price"]
    if "size" in update_data:
        product.size = update_data["size"].strip() if update_data["size"] else None
    if "color" in update_data:
        product.color = update_data["color"].strip() if update_data["color"] else None
    if "image_url" in update_data:
        product.image_url = update_data["image_url"].strip() if update_data["image_url"] else None
    if "stock_quantity" in update_data and update_data["stock_quantity"] is not None:
        product.stock_quantity = update_data["stock_quantity"]
    if "is_available" in update_data and update_data["is_available"] is not None:
        product.is_available = update_data["is_available"]

    try:
        db.commit()
        db.refresh(product)
        logger.info(f"Updated product ID {product_id}")
        return product
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        logger.error(f"Error updating product ID {product_id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error occurred while updating the product.",
        )


@router.delete(
    "/{product_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete a product",
    description="Permanently deletes a product from the database.",
)
def delete_product(
    product_id: int,
    db: Session = Depends(get_db_session),
):
    """
    Deletes a product by ID. Returns 404 if not found.
    """
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID {product_id} not found.",
        )

    product_name = product.product_name
    try:
        db.delete(product)
        db.commit()
        logger.info(f"Deleted product ID {product_id} ('{product_name}')")
        return {
            "message": f"Product with ID {product_id} ('{product_name}') was successfully deleted.",
            "deleted_id": product_id,
            "status": "success",
        }
    except Exception as exc:
        db.rollback()
        logger.error(f"Error deleting product ID {product_id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error occurred while deleting the product.",
        )

