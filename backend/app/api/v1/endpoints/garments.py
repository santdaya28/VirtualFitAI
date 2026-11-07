from typing import Optional, List, Annotated
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.core.database import get_db
from app.models.garment import Garment
from app.schemas.garment import (
    GarmentResponse,
    GarmentCreate,
    GarmentUpdate,
    GarmentListResponse,
)

router = APIRouter()

# Default seed garments matching frontend catalogue
SEED_GARMENTS = [
    {
        "id": 1,
        "name": "Midnight Navy Slim Blazer",
        "category": "Formal",
        "price": 189.0,
        "fit_type": "Slim Fit",
        "color": "Navy Blue",
        "badge": "Popular",
        "description": "Structured lightweight wool-blend blazer tailored for modern business and evening wear.",
        "image_url": "https://images.unsplash.com/photo-1507679799987-c73779587ccf?auto=format&fit=crop&w=800&q=80",
        "is_active": True,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    },
    {
        "id": 2,
        "name": "Oversized Silk Linen Camp Shirt",
        "category": "Casual",
        "price": 79.0,
        "fit_type": "Relaxed Fit",
        "color": "Sand Beige",
        "badge": "Trending",
        "description": "Breathable linen-silk blend with relaxed camp collar, ideal for warm seasons.",
        "image_url": "https://images.unsplash.com/photo-1596755094514-f87e34085b2c?auto=format&fit=crop&w=800&q=80",
        "is_active": True,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    },
    {
        "id": 3,
        "name": "Royal Heritage Embroidered Kurta",
        "category": "Ethnic",
        "price": 129.0,
        "fit_type": "Regular Fit",
        "color": "Deep Wine",
        "badge": "New Arrival",
        "description": "Intricately embroidered mandarin collar kurta crafted in premium art silk.",
        "image_url": "https://images.unsplash.com/photo-1583391733956-3750e0ff4e8b?auto=format&fit=crop&w=800&q=80",
        "is_active": True,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    },
    {
        "id": 4,
        "name": "Minimalist Charcoal Trench Coat",
        "category": "Outerwear",
        "price": 240.0,
        "fit_type": "Tailored Fit",
        "color": "Charcoal Grey",
        "badge": "Premium",
        "description": "Water-resistant double-breasted trench coat with storm flap and removable belt.",
        "image_url": "https://images.unsplash.com/photo-1544441893-675973e31985?auto=format&fit=crop&w=800&q=80",
        "is_active": True,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    },
    {
        "id": 5,
        "name": "Textured Knit Merino Sweater",
        "category": "Casual",
        "price": 95.0,
        "fit_type": "Classic Fit",
        "color": "Forest Green",
        "badge": "Best Seller",
        "description": "Ultra-fine Australian merino wool knit with ribbed cuffs and subtle waffle texture.",
        "image_url": "https://images.unsplash.com/photo-1620799140408-edc6dcb6d633?auto=format&fit=crop&w=800&q=80",
        "is_active": True,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    },
    {
        "id": 6,
        "name": "Classic Double-Breasted Suit",
        "category": "Formal",
        "price": 320.0,
        "fit_type": "Bespoke Fit",
        "color": "Slate Grey",
        "badge": "Signature",
        "description": "Handcrafted Italian wool two-piece formal suit with sharp peaked lapels.",
        "image_url": "https://images.unsplash.com/photo-1594938298603-c8148c4dae35?auto=format&fit=crop&w=800&q=80",
        "is_active": True,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    },
    {
        "id": 7,
        "name": "Zari Border Silk Sherwani",
        "category": "Ethnic",
        "price": 210.0,
        "fit_type": "Traditional Fit",
        "color": "Ivory Gold",
        "badge": "Festive",
        "description": "Regal raw silk sherwani adorned with handcrafted zari thread embroidery.",
        "image_url": "https://images.unsplash.com/photo-1610030469983-98e550d6193c?auto=format&fit=crop&w=800&q=80",
        "is_active": True,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    },
    {
        "id": 8,
        "name": "Insulated Quilted Puffer Jacket",
        "category": "Outerwear",
        "price": 175.0,
        "fit_type": "Regular Fit",
        "color": "Matte Black",
        "badge": "Winter",
        "description": "Thermal down-alternative insulated jacket with high stand collar and fleece pockets.",
        "image_url": "https://images.unsplash.com/photo-1548883354-7622d03aca27?auto=format&fit=crop&w=800&q=80",
        "is_active": True,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    },
]

AVAILABLE_CATEGORIES = ["Formal", "Casual", "Ethnic", "Outerwear"]

@router.get("", response_model=GarmentListResponse, summary="List catalogue garments")
def list_garments(
    category: Annotated[Optional[str], Query(description="Filter by category (Formal, Casual, Ethnic, Outerwear)")] = None,
    search: Annotated[Optional[str], Query(description="Search garment name or description")] = None,
    db: Optional[Session] = Depends(get_db),
):
    """
    Returns catalogue garments with optional category and search filters.
    If PostgreSQL is connected and populated, queries live records; otherwise falls back to seed catalogue.
    """
    items: List[GarmentResponse] = []

    # Try querying PostgreSQL if available
    if db is not None:
        try:
            stmt = select(Garment).where(Garment.is_active == True)
            if category and category.lower() != "all":
                stmt = stmt.where(Garment.category.ilike(category))
            if search:
                stmt = stmt.where(Garment.name.ilike(f"%{search}%"))

            db_garments = db.scalars(stmt).all()
            if db_garments:
                items = [GarmentResponse.model_validate(g) for g in db_garments]
        except Exception:
            # Fallback to seed if database table does not exist or connection fails
            items = []

    # Fallback to in-memory seed garments if database returned nothing
    if not items:
        filtered = SEED_GARMENTS
        if category and category.lower() != "all":
            filtered = [g for g in filtered if g["category"].lower() == category.lower()]
        if search:
            s = search.lower()
            filtered = [g for g in filtered if s in g["name"].lower() or s in (g["description"] or "").lower()]

        items = [GarmentResponse(**g) for g in filtered]

    return GarmentListResponse(
        total=len(items),
        items=items,
        categories=AVAILABLE_CATEGORIES,
    )

@router.get("/{garment_id}", response_model=GarmentResponse, summary="Get single garment details")
def get_garment(garment_id: int, db: Optional[Session] = Depends(get_db)):
    """
    Get garment details by ID.
    """
    if db is not None:
        try:
            garment = db.get(Garment, garment_id)
            if garment and garment.is_active:
                return GarmentResponse.model_validate(garment)
        except Exception:
            pass

    # Search seed catalogue fallback
    matched = next((g for g in SEED_GARMENTS if g["id"] == garment_id), None)
    if matched:
        return GarmentResponse(**matched)

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Garment with ID {garment_id} not found")

@router.post("", response_model=GarmentResponse, status_code=status.HTTP_201_CREATED, summary="Add new garment to inventory")
def create_garment(garment_in: GarmentCreate, db: Optional[Session] = Depends(get_db)):
    """
    Create a new garment. Persists to PostgreSQL when online, or registers to local collection.
    """
    if db is not None:
        try:
            db_garment = Garment(**garment_in.model_dump())
            db.add(db_garment)
            db.commit()
            db.refresh(db_garment)
            return GarmentResponse.model_validate(db_garment)
        except Exception as exc:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Database error while saving garment: {str(exc)}"
            )

    # In-memory addition fallback
    new_id = len(SEED_GARMENTS) + 1
    new_item = {
        "id": new_id,
        **garment_in.model_dump(),
        "is_active": True,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    SEED_GARMENTS.append(new_item)
    return GarmentResponse(**new_item)

