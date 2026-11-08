import logging
from typing import List, Optional, Annotated
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.database import get_db
from app.models import Shop
from app.schemas.shop import (
    ShopCreate,
    ShopUpdate,
    ShopResponse,
)

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


@router.post(
    "",
    response_model=ShopResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new shop",
    description="Registers a new retail garment boutique/shop in the database.",
)
def create_shop(
    shop_in: ShopCreate,
    db: Session = Depends(get_db_session),
):
    """
    Creates a new Shop entry. shop_name is required.
    """
    clean_name = shop_in.shop_name.strip()
    if not clean_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Shop name cannot be empty or whitespace.",
        )

    try:
        new_shop = Shop(
            shop_name=clean_name,
            owner_name=shop_in.owner_name.strip() if shop_in.owner_name else None,
            email=shop_in.email.strip().lower() if shop_in.email else None,
            phone=shop_in.phone.strip() if shop_in.phone else None,
            address=shop_in.address.strip() if shop_in.address else None,
        )
        db.add(new_shop)
        db.commit()
        db.refresh(new_shop)
        logger.info(f"Created new shop ID {new_shop.id}: '{new_shop.shop_name}'")
        return new_shop
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
    description="Retrieves a paginated list of registered shops.",
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
    return shops


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
    return shop


@router.put(
    "/{shop_id}",
    response_model=ShopResponse,
    summary="Update shop details",
    description="Updates one or more fields of an existing shop.",
)
def update_shop(
    shop_id: int,
    shop_update: ShopUpdate,
    db: Session = Depends(get_db_session),
):
    """
    Updates editable fields for a shop. Returns 404 if shop does not exist.
    """
    shop = db.get(Shop, shop_id)
    if not shop:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Shop with ID {shop_id} not found.",
        )

    update_data = shop_update.model_dump(exclude_unset=True)
    if not update_data:
        # Nothing provided to update, return unchanged
        return shop

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
        return shop
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
    db: Session = Depends(get_db_session),
):
    """
    Removes a shop by ID. All associated products are removed via cascading foreign key.
    Returns 404 if shop does not exist.
    """
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

