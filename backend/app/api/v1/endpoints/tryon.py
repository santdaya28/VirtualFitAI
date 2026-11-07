import uuid
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.core.database import get_db
from app.models.tryon_session import TryOnSession
from app.models.garment import Garment
from app.schemas.tryon import (
    TryOnCreateRequest,
    TryOnSessionResponse,
    TryOnStatusResponse,
)
from app.services.tryon_adapter import get_tryon_adapter
from app.api.v1.endpoints.garments import SEED_GARMENTS

router = APIRouter()

# In-memory store fallback when PostgreSQL is offline
IN_MEMORY_SESSIONS: dict = {}

@router.post("", response_model=TryOnSessionResponse, status_code=status.HTTP_201_CREATED, summary="Submit a Virtual Try-On task")
def create_tryon_session(
    request: TryOnCreateRequest,
    db: Optional[Session] = Depends(get_db),
):
    """
    Submits a customer photo and selected garment to the configured AI Try-On pipeline.
    """
    adapter = get_tryon_adapter()

    # Find garment details to get image URL
    garment_image_url = ""
    garment_category = None

    if db is not None:
        try:
            db_garment = db.get(Garment, request.garment_id)
            if db_garment:
                garment_image_url = db_garment.image_url
                garment_category = db_garment.category
        except Exception:
            pass

    if not garment_image_url:
        matched = next((g for g in SEED_GARMENTS if g["id"] == request.garment_id), None)
        if matched:
            garment_image_url = matched["image_url"]
            garment_category = matched["category"]
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Garment with ID {request.garment_id} not found"
            )

    # Submit task to adapter
    try_result = adapter.submit_tryon(
        customer_photo_url=request.customer_photo_url,
        garment_image_url=garment_image_url,
        category=garment_category,
    )

    session_id = try_result.get("session_id", str(uuid.uuid4()))
    provider = try_result.get("provider", "mock")
    init_status = try_result.get("status", "processing")

    session_data = {
        "id": session_id,
        "customer_photo_url": request.customer_photo_url,
        "garment_id": request.garment_id,
        "status": init_status,
        "result_image_url": try_result.get("result_image_url"),
        "provider": provider,
        "error_message": None,
        "created_at": datetime.now(timezone.utc),
    }

    # Persist in DB if available
    if db is not None:
        try:
            db_session = TryOnSession(**session_data)
            db.add(db_session)
            db.commit()
            db.refresh(db_session)
            return TryOnSessionResponse.model_validate(db_session)
        except Exception:
            db.rollback()

    # In-memory fallback
    IN_MEMORY_SESSIONS[session_id] = session_data
    return TryOnSessionResponse(**session_data)

@router.get("/{session_id}", response_model=TryOnStatusResponse, summary="Check Try-On task status")
def get_tryon_status(session_id: str, db: Optional[Session] = Depends(get_db)):
    """
    Checks the current progress and result of a virtual try-on task.
    """
    adapter = get_tryon_adapter()

    # Check adapter progress
    status_info = adapter.check_status(session_id)

    # Update in DB if available
    if db is not None:
        try:
            db_session = db.get(TryOnSession, session_id)
            if db_session:
                db_session.status = status_info.get("status", db_session.status)
                if status_info.get("result_image_url"):
                    db_session.result_image_url = status_info["result_image_url"]
                db.commit()
        except Exception:
            pass

    # Update in memory
    if session_id in IN_MEMORY_SESSIONS:
        IN_MEMORY_SESSIONS[session_id]["status"] = status_info.get("status", IN_MEMORY_SESSIONS[session_id]["status"])
        if status_info.get("result_image_url"):
            IN_MEMORY_SESSIONS[session_id]["result_image_url"] = status_info["result_image_url"]

    return TryOnStatusResponse(
        session_id=session_id,
        status=status_info.get("status", "processing"),
        progress_percentage=status_info.get("progress_percentage", 50),
        message=status_info.get("message", "Processing virtual try-on"),
        result_image_url=status_info.get("result_image_url"),
    )

