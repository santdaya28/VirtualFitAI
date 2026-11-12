import uuid
import logging
from pathlib import Path
from typing import List, Optional, Annotated
from fastapi import APIRouter, Depends, HTTPException, Query, status, Request, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.database import get_db
from app.models import Shop, Product, User
from app.core.security import get_optional_user, get_current_user
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


UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_IMAGE_MIME_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/pjpeg",
    "image/png",
    "image/x-png",
    "image/webp",
}
MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB


def _validate_image_magic_bytes(contents: bytes) -> str:
    """
    Validates image binary content against standard magic byte signatures.
    """
    if len(contents) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )
    if contents.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    elif contents.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    elif contents.startswith(b"RIFF") and len(contents) >= 12 and contents[8:12] == b"WEBP":
        return ".webp"
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Invalid image format. File content does not match valid JPEG, PNG, or WebP headers.",
    )


@router.post(
    "/upload-image",
    summary="Upload product image",
    description="Uploads a garment product photo (max 5 MB, JPG/JPEG/PNG/WebP), saves it in the backend uploads directory, and returns its public URL.",
)
async def upload_image(
    request: Request,
    file: UploadFile = File(...),
    current_user: Optional[User] = Depends(get_optional_user),
):
    """
    Handles safe image uploads for garments.
    Requires authenticated shop owner or admin.
    Validates file extension, MIME type, magic bytes, and size limit (5 MB).
    Generates a secure UUID-based filename.
    """
    user = current_user if isinstance(current_user, User) else None
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required to upload garment photos. Please provide a valid Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if user.role == "customer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Customers cannot upload catalogue photos. Shop owner role required.",
        )

    filename = file.filename or "upload.jpg"
    ext = Path(filename).suffix.lower()

    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported image extension '{ext}'. Allowed extensions: {', '.join(sorted(ALLOWED_IMAGE_EXTENSIONS))}.",
        )

    if file.content_type and file.content_type.lower() not in ALLOWED_IMAGE_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid content type '{file.content_type}'. Must be a valid image (JPG, PNG, or WebP).",
        )

    contents = await file.read()
    if len(contents) > MAX_IMAGE_SIZE_BYTES:
        size_mb = len(contents) / (1024 * 1024)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Image size ({size_mb:.2f} MB) exceeds the 5 MB limit.",
        )

    # Validate magic bytes
    detected_ext = _validate_image_magic_bytes(contents)
    actual_ext = detected_ext if detected_ext else ext

    # Generate safe unique filename
    unique_filename = f"{uuid.uuid4().hex}{actual_ext}"
    target_path = UPLOAD_DIR / unique_filename

    try:
        with open(target_path, "wb") as f:
            f.write(contents)
    except Exception as exc:
        logger.error(f"Failed to write uploaded image file: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save image file on server.",
        )

    # Generate public static URL
    base_url = str(request.base_url).rstrip("/")
    image_url = f"{base_url}/uploads/{unique_filename}"
    logger.info(f"Uploaded product image: {unique_filename} ({len(contents)} bytes) by user {user.id} -> {image_url}")

    return {
        "image_url": image_url,
        "filename": unique_filename,
        "size_bytes": len(contents),
        "content_type": file.content_type or f"image/{actual_ext.lstrip('.')}",
        "status": "success",
    }


@router.post(
    "",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new garment product",
    description="Adds a new garment item to the catalogue associated with a registered shop.",
)
def create_product(
    product_in: ProductCreate,
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db_session),
):
    """
    Creates a new Product.
    Validates that the referenced shop_id exists in the database.
    Enforces shop data isolation: shop owners cannot add products to other shops.
    """
    # Authorization & Shop isolation
    user = current_user if isinstance(current_user, User) else None
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required to create products. Please provide a valid Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if user.role == "customer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Customers cannot create products. Shop owner role required.",
        )
    if user.role == "shop_owner":
        if user.shop_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cross-shop access violation: Your account is not associated with any shop.",
            )
        if product_in.shop_id is not None and product_in.shop_id != user.shop_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Cross-shop access violation: You can only add products to your own shop (ID: {user.shop_id}).",
            )
        target_shop_id = user.shop_id
    else:
        if product_in.shop_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="shop_id is required when creating a product as an administrator.",
            )
        target_shop_id = product_in.shop_id

    # 1. Validate that the parent Shop exists
    parent_shop = db.get(Shop, target_shop_id)
    if not parent_shop:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot create product: Shop with ID {target_shop_id} does not exist.",
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
            shop_id=target_shop_id,
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
    "/my",
    response_model=List[ProductResponse],
    summary="List products owned by authenticated shop",
    description="Returns all products (including unpublished drafts) belonging strictly to the signed-in shop owner.",
)
def list_my_products(
    category: Annotated[Optional[str], Query(description="Filter products by category")] = None,
    search: Annotated[Optional[str], Query(description="Search by product name or description")] = None,
    is_available: Annotated[Optional[bool], Query(description="Filter by active/published status")] = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    if current_user.role != "shop_owner" or current_user.shop_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only authenticated shop owners with an assigned shop can access shop inventory.",
        )

    stmt = select(Product).where(Product.shop_id == current_user.shop_id)
    if is_available is not None:
        stmt = stmt.where(Product.is_available == is_available)
    if category and category.strip():
        stmt = stmt.where(Product.category.ilike(f"%{category.strip()}%"))
    if search and search.strip():
        term = f"%{search.strip()}%"
        stmt = stmt.where(Product.product_name.ilike(term) | Product.description.ilike(term))
    stmt = stmt.order_by(Product.id.desc()).offset(skip).limit(limit)
    return db.scalars(stmt).all()


@router.get(
    "",
    response_model=List[ProductResponse],
    summary="List garment products for a specific shop",
    description="Retrieves products scoped strictly to a single storefront (shop_id or shop_slug, or owning shop account).",
)
def list_products(
    shop_id: Annotated[Optional[int], Query(description="Filter products belonging to a specific shop ID")] = None,
    shop_slug: Annotated[Optional[str], Query(description="Filter products belonging to a specific storefront slug")] = None,
    category: Annotated[Optional[str], Query(description="Filter products by category (case-insensitive substring)")] = None,
    search: Annotated[Optional[str], Query(description="Search by product name or description (case-insensitive)")] = None,
    is_available: Annotated[Optional[bool], Query(description="Filter by active/published availability status")] = None,
    skip: Annotated[int, Query(ge=0, description="Number of records to skip for pagination")] = 0,
    limit: Annotated[int, Query(ge=1, le=100, description="Maximum number of records to return per page")] = 20,
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db_session),
):
    """
    Lists products strictly isolated to a single shop context.
    """
    user = current_user if isinstance(current_user, User) else None
    clean_slug = shop_slug.strip().lower() if isinstance(shop_slug, str) and shop_slug.strip() else None
    req_shop_id = shop_id if isinstance(shop_id, int) else None

    resolved_shop_id: Optional[int] = None
    if clean_slug is not None:
        slug_shop = db.scalar(select(Shop).where(func.lower(Shop.slug) == clean_slug))
        if not slug_shop:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Storefront '{clean_slug}' not found.",
            )
        if req_shop_id is not None and slug_shop.id != req_shop_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Conflicting shop_id and shop_slug query parameters.",
            )
        resolved_shop_id = slug_shop.id
    elif req_shop_id is not None:
        resolved_shop_id = req_shop_id
    elif user is not None and user.role == "shop_owner" and user.shop_id is not None:
        resolved_shop_id = user.shop_id
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Storefront context (shop_id or shop_slug) is required. Global cross-shop listings are disabled.",
        )

    if user is not None and user.role == "shop_owner":
        if user.shop_id is None or resolved_shop_id != user.shop_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Cross-shop access violation: Shop owners cannot query Shop ID {resolved_shop_id} inventory.",
            )

    is_owner_or_admin = bool(
        user is not None
        and (
            user.role == "admin"
            or (user.role == "shop_owner" and user.shop_id == resolved_shop_id)
        )
    )

    stmt = select(Product).where(Product.shop_id == resolved_shop_id)

    if is_owner_or_admin:
        if is_available is not None:
            stmt = stmt.where(Product.is_available == is_available)
    else:
        stmt = stmt.where(Product.is_available.is_(True))

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
    description="Retrieves detailed information for a specific product by its ID with optional shop ownership checks.",
)
def get_product(
    product_id: int,
    shop_id: Annotated[Optional[int], Query(description="Expected owning shop ID")] = None,
    shop_slug: Annotated[Optional[str], Query(description="Expected owning storefront slug")] = None,
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db_session),
):
    """
    Returns a single product by primary key ID, enforcing storefront ownership when scoped or authenticated.
    """
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID {product_id} not found.",
        )

    user = current_user if isinstance(current_user, User) else None
    clean_slug = shop_slug.strip().lower() if isinstance(shop_slug, str) and shop_slug.strip() else None
    req_shop_id = shop_id if isinstance(shop_id, int) else None

    if clean_slug is not None:
        slug_shop = db.scalar(select(Shop).where(func.lower(Shop.slug) == clean_slug))
        if not slug_shop:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Storefront '{clean_slug}' not found.",
            )
        if product.shop_id != slug_shop.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Cross-shop access violation: Product ID {product_id} does not belong to storefront '{clean_slug}'.",
            )
    if req_shop_id is not None and product.shop_id != req_shop_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Cross-shop access violation: Product ID {product_id} does not belong to Shop ID {req_shop_id}.",
        )

    if user is not None and user.role == "shop_owner":
        if user.shop_id is None or product.shop_id != user.shop_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Cross-shop access violation: You do not own product {product_id} (Shop ID: {product.shop_id}).",
            )

    is_owner_or_admin = bool(
        user is not None
        and (
            user.role == "admin"
            or (user.role == "shop_owner" and user.shop_id == product.shop_id)
        )
    )
    if not product.is_available and not is_owner_or_admin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID {product_id} is not available.",
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
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db_session),
):
    """
    Updates editable fields of a product.
    Enforces shop data isolation: shop owners cannot edit other shops' products.
    """
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID {product_id} not found.",
        )

    # Authorization & Shop isolation
    user = current_user if isinstance(current_user, User) else None
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required to edit products. Please provide a valid Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if user.role == "customer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Customers cannot edit products. Shop owner role required.",
        )
    if user.role == "shop_owner":
        if user.shop_id is None or product.shop_id != user.shop_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Cross-shop access violation: You do not own product {product_id} (Shop ID: {product.shop_id}).",
            )


    update_data = product_update.model_dump(exclude_unset=True)
    if not update_data:
        return product

    # Disallow moving products between shops to maintain strict shop ownership isolation
    if "shop_id" in update_data and update_data["shop_id"] is not None:
        target_shop_id = update_data["shop_id"]
        if target_shop_id != product.shop_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Cross-shop access violation: Products cannot be transferred to another shop (attempted Shop ID {target_shop_id}).",
            )

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
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db_session),
):
    """
    Deletes a product by ID.
    Enforces shop data isolation: shop owners cannot delete other shops' products.
    """
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID {product_id} not found.",
        )

    # Authorization & Shop isolation
    user = current_user if isinstance(current_user, User) else None
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required to delete products. Please provide a valid Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if user.role == "customer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Customers cannot delete products. Shop owner role required.",
        )
    if user.role == "shop_owner":
        if user.shop_id is None or product.shop_id != user.shop_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Cross-shop access violation: You do not own product {product_id} (Shop ID: {product.shop_id}).",
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

