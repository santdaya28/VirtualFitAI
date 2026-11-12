import logging
from typing import List, Optional, Annotated
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.database import get_db
from app.models import Shop, User, Product
from app.core.security import get_optional_user
from app.core.slugs import generate_unique_shop_slug, normalize_explicit_slug
from app.schemas.shop import (
    ShopCreate,
    ShopUpdate,
    ShopResponse,
)
from app.schemas.product import ProductResponse

logger = logging.getLogger("virtualfit.shops")

router = APIRouter(prefix="/api/shops", tags=["Shops"])


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


def _get_published_product_counts(db: Session, shop_ids: List[int]) -> dict[int, int]:
    """Return mapping of shop_id -> published product count."""
    if not shop_ids:
        return {}
    rows = db.execute(
        select(Product.shop_id, func.count(Product.id))
        .where(Product.shop_id.in_(shop_ids), Product.is_available.is_(True))
        .group_by(Product.shop_id)
    ).all()
    return {int(row[0]): int(row[1]) for row in rows}


def _to_shop_response(shop: Shop, product_count: int = 0) -> ShopResponse:
    """Serialize a Shop ORM model with published product count."""
    return ShopResponse(
        id=shop.id,
        shop_name=shop.shop_name,
        owner_name=shop.owner_name,
        email=shop.email,
        phone=shop.phone,
        address=shop.address,
        slug=shop.slug,
        product_count=product_count,
        created_at=shop.created_at,
    )


def _get_shop_by_slug_or_404(db: Session, shop_slug: str) -> Shop:
    """Resolve a Shop by its URL-safe storefront slug (case-insensitive)."""
    clean_slug = (shop_slug or "").strip().lower()
    if not clean_slug:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Storefront slug cannot be empty.",
        )
    shop = db.scalar(select(Shop).where(func.lower(Shop.slug) == clean_slug))
    if not shop:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Storefront '{clean_slug}' not found.",
        )
    return shop


@router.post(
    "",
    response_model=ShopResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new shop",
    description="Registers a new retail garment boutique/shop in the database.",
)
def create_shop(
    shop_in: ShopCreate,
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db_session),
):
    """
    Creates a new Shop entry for an authorized shop owner or admin.
    """
    user = current_user if isinstance(current_user, User) else None
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required to create a shop.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if user.role == "customer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Customers cannot create shop storefronts. Register a shop-owner account instead.",
        )
    if user.role == "shop_owner" and user.shop_id is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Your account already manages Shop ID {user.shop_id}. Cross-shop creation is not permitted.",
        )

    clean_name = shop_in.shop_name.strip()
    if not clean_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Shop name cannot be empty or whitespace.",
        )

    try:
        new_shop = Shop(
            shop_name=clean_name,
            slug=generate_unique_shop_slug(db, clean_name),
            owner_name=shop_in.owner_name.strip() if shop_in.owner_name else None,
            email=shop_in.email.strip().lower() if shop_in.email else None,
            phone=shop_in.phone.strip() if shop_in.phone else None,
            address=shop_in.address.strip() if shop_in.address else None,
        )
        db.add(new_shop)
        db.flush()
        if user.role == "shop_owner" and user.shop_id is None:
            user.shop_id = new_shop.id
        db.commit()
        db.refresh(new_shop)
        logger.info(f"Created new shop ID {new_shop.id}: '{new_shop.shop_name}' (slug='{new_shop.slug}')")
        return _to_shop_response(new_shop, product_count=0)
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        logger.error(f"Error creating shop: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error occurred while creating the shop.",
        )


@router.get(
    "",
    response_model=List[ShopResponse],
    summary="List all shops",
    description="Retrieves a paginated list of registered shops with storefront slugs and published counts.",
)
def list_shops(
    skip: Annotated[int, Query(ge=0, description="Number of records to skip")] = 0,
    limit: Annotated[int, Query(ge=1, le=100, description="Maximum number of records to return")] = 20,
    search: Annotated[Optional[str], Query(description="Search shops by name, owner, or email")] = None,
    db: Session = Depends(get_db_session),
):
    """
    Lists shops with pagination and optional search filter.
    """
    stmt = select(Shop)
    if search and search.strip():
        term = f"%{search.strip()}%"
        stmt = stmt.where(
            Shop.shop_name.ilike(term)
            | Shop.owner_name.ilike(term)
            | Shop.email.ilike(term)
        )

    stmt = stmt.order_by(Shop.id.asc()).offset(skip).limit(limit)
    shops = db.scalars(stmt).all()
    counts = _get_published_product_counts(db, [s.id for s in shops])
    return [_to_shop_response(s, product_count=counts.get(s.id, 0)) for s in shops]


@router.get(
    "/slug/{shop_slug}",
    response_model=ShopResponse,
    summary="Get shop details by storefront slug",
    description="Retrieves public boutique details for a specific storefront slug.",
)
def get_shop_by_slug(
    shop_slug: str,
    db: Session = Depends(get_db_session),
):
    shop = _get_shop_by_slug_or_404(db, shop_slug)
    counts = _get_published_product_counts(db, [shop.id])
    return _to_shop_response(shop, product_count=counts.get(shop.id, 0))


@router.get(
    "/slug/{shop_slug}/products",
    response_model=List[ProductResponse],
    summary="List published products for a specific shop storefront",
    description="Returns strictly the published (is_available=true) garments owned by this shop storefront.",
)
def list_storefront_products(
    shop_slug: str,
    category: Annotated[Optional[str], Query(description="Filter products by category")] = None,
    search: Annotated[Optional[str], Query(description="Search products in this shop")] = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    db: Session = Depends(get_db_session),
):
    shop = _get_shop_by_slug_or_404(db, shop_slug)
    stmt = select(Product).where(
        Product.shop_id == shop.id,
        Product.is_available.is_(True),
    )
    if category and category.strip():
        stmt = stmt.where(Product.category.ilike(f"%{category.strip()}%"))
    if search and search.strip():
        term = f"%{search.strip()}%"
        stmt = stmt.where(Product.product_name.ilike(term) | Product.description.ilike(term))
    stmt = stmt.order_by(Product.id.desc()).offset(skip).limit(limit)
    return db.scalars(stmt).all()


@router.get(
    "/slug/{shop_slug}/products/{product_id}",
    response_model=ProductResponse,
    summary="Get single storefront product by slug and ID",
    description="Verifies that the product exists, is published, and belongs to the requested shop storefront.",
)
def get_storefront_product(
    shop_slug: str,
    product_id: int,
    db: Session = Depends(get_db_session),
):
    shop = _get_shop_by_slug_or_404(db, shop_slug)
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID {product_id} not found.",
        )
    if product.shop_id != shop.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Cross-shop access violation: Product ID {product_id} does not belong to storefront '{shop.slug}'.",
        )
    if not product.is_available:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product ID {product_id} is not currently published in storefront '{shop.slug}'.",
        )
    return product


@router.get(
    "/{shop_id}",
    response_model=ShopResponse,
    summary="Get shop details by ID",
    description="Retrieves detailed profile information for a specific shop.",
)
def get_shop(
    shop_id: int,
    db: Session = Depends(get_db_session),
):
    """
    Returns single shop by primary key ID. Returns 404 if not found.
    """
    shop = db.get(Shop, shop_id)
    if not shop:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Shop with ID {shop_id} not found.",
        )
    counts = _get_published_product_counts(db, [shop.id])
    return _to_shop_response(shop, product_count=counts.get(shop.id, 0))


@router.put(
    "/{shop_id}",
    response_model=ShopResponse,
    summary="Update shop details",
    description="Updates one or more fields of an existing shop.",
)
def update_shop(
    shop_id: int,
    shop_update: ShopUpdate,
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db_session),
):
    """
    Updates editable fields for a shop.
    Enforces shop isolation: shop owners can only manage their own shop profile.
    """
    shop = db.get(Shop, shop_id)
    if not shop:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Shop with ID {shop_id} not found.",
        )

    # Authorization & Shop isolation
    user = current_user if isinstance(current_user, User) else None
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required to update shop profile. Please provide a valid Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if user.role == "customer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Customers cannot update shop profiles. Shop owner role required.",
        )
    if user.role == "shop_owner" and user.shop_id is not None:
        if shop_id != user.shop_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Cross-shop access violation: You do not have permission to manage Shop ID {shop_id}.",
            )


    update_data = shop_update.model_dump(exclude_unset=True)
    if not update_data:
        counts = _get_published_product_counts(db, [shop.id])
        return _to_shop_response(shop, product_count=counts.get(shop.id, 0))

    if "slug" in update_data:
        raw_slug = update_data["slug"]
        if raw_slug is not None:
            try:
                normalized_slug = normalize_explicit_slug(raw_slug)
            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=str(exc),
                )
            conflict = db.scalar(
                select(Shop.id).where(func.lower(Shop.slug) == normalized_slug, Shop.id != shop_id)
            )
            if conflict is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Storefront slug '{normalized_slug}' is already in use by another shop.",
                )
            shop.slug = normalized_slug

    if "shop_name" in update_data:
        val = update_data["shop_name"]
        if val is not None:
            clean_name = val.strip()
            if not clean_name:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Shop name cannot be set to empty or whitespace.",
                )
            shop.shop_name = clean_name
            if not shop.slug:
                shop.slug = generate_unique_shop_slug(db, clean_name, exclude_shop_id=shop.id)

    if "owner_name" in update_data:
        shop.owner_name = update_data["owner_name"].strip() if update_data["owner_name"] else None
    if "email" in update_data:
        shop.email = update_data["email"].strip().lower() if update_data["email"] else None
    if "phone" in update_data:
        shop.phone = update_data["phone"].strip() if update_data["phone"] else None
    if "address" in update_data:
        shop.address = update_data["address"].strip() if update_data["address"] else None

    try:
        db.commit()
        db.refresh(shop)
        logger.info(f"Updated shop ID {shop_id}")
        counts = _get_published_product_counts(db, [shop.id])
        return _to_shop_response(shop, product_count=counts.get(shop.id, 0))
    except Exception as exc:
        db.rollback()
        logger.error(f"Error updating shop ID {shop_id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error occurred while updating the shop.",
        )


@router.delete(
    "/{shop_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete a shop",
    description="Deletes a shop and all associated products (cascading).",
)
def delete_shop(
    shop_id: int,
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db_session),
):
    """
    Removes a shop by ID. Only the owning shop owner or an admin may delete the shop.
    """
    user = current_user if isinstance(current_user, User) else None
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required to delete a shop.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if user.role == "customer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Customers cannot delete shop storefronts.",
        )
    if user.role == "shop_owner" and (user.shop_id is None or shop_id != user.shop_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Cross-shop access violation: You do not have permission to delete Shop ID {shop_id}.",
        )

    shop = db.get(Shop, shop_id)
    if not shop:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Shop with ID {shop_id} not found.",
        )

    shop_name = shop.shop_name
    try:
        db.delete(shop)
        db.commit()
        logger.info(f"Deleted shop ID {shop_id} ('{shop_name}')")
        return {
            "message": f"Shop with ID {shop_id} ('{shop_name}') was successfully deleted.",
            "deleted_id": shop_id,
            "status": "success",
        }
    except Exception as exc:
        db.rollback()
        logger.error(f"Error deleting shop ID {shop_id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error occurred while deleting the shop.",
        )

