from datetime import datetime, timedelta, date
from io import BytesIO
from pathlib import Path
from typing import Optional
import hashlib
import io
import os
import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from fastapi.responses import FileResponse, StreamingResponse
from PIL import Image as PILImage, UnidentifiedImageError
from pydantic import BaseModel, Field
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from core.dependencies import get_current_user, require_admin, require_guard
from core.security import hash_password
from db.session import get_db
from models import Alert, Entry, Gate, SystemState, User, Visitor
from utils.qr import QR_DIR, generate_qr_hash, generate_qr_image
from services.audit_service import record_audit


router = APIRouter()


# ══════════════════════════════════════════════════════════════════════════════
# FEATURE 3 — PHOTO UPLOAD
# ═════════════════════════════════════════════════════════════════════PHOTO_DIR = Path(__file__).resolve().parents[3] / "static" / "photos"
MAX_PHOTO_BYTES = 5 * 1024 * 1024
ALLOWED_PHOTO_TYPES = {"image/jpeg", "image/png", "image/webp"}


@router.post("/users/{user_id}/photo")
async def upload_photo(
    user_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    if current.role != "admin" and current.id != user_id:
        raise HTTPException(status_code=403, detail="Can only upload your own photo")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if file.content_type not in ALLOWED_PHOTO_TYPES:
        raise HTTPException(status_code=415, detail="Only JPEG, PNG, and WebP images are accepted")

    content = await file.read(MAX_PHOTO_BYTES + 1)
    await file.close()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded image is empty")
    if len(content) > MAX_PHOTO_BYTES:
        raise HTTPException(status_code=413, detail="Photo must not exceed 5 MB")

    try:
        with PILImage.open(BytesIO(content)) as image:
            image.verify()
        with PILImage.open(BytesIO(content)) as image:
            image = image.convert("RGB")
            image.thumbnail((1600, 1600), PILImage.Resampling.LANCZOS)
            PHOTO_DIR.mkdir(parents=True, exist_ok=True)
            filename = f"user-{user.id}-{uuid.uuid4().hex}.jpg"
            destination = PHOTO_DIR / filename
            image.save(destination, format="JPEG", quality=88, optimize=True)
    except (UnidentifiedImageError, OSError, ValueError, PILImage.DecompressionBombError):
        raise HTTPException(status_code=400, detail="Uploaded file is not a valid image")

    previous_photo = user.photo
    user.photo = f"/static/photos/{filename}"
    try:
        record_audit(db, current, "user.photo_upload", "user", user_id)
        db.commit()
    except Exception:
        db.rollback()
        destination.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail="Could not save photo record")

    if previous_photo:
        old_path = PHOTO_DIR / Path(previous_photo).name
        if old_path != destination:
            old_path.unlink(missing_ok=True)
            for variant in ("thumb", "small"):
                (PHOTO_DIR / f"{old_path.stem}_{variant}.jpg").unlink(missing_ok=True)

    return {"photo_url": user.photo}


@router.get("/users/{user_id}/photo")
def get_photo(
    user_id: int,
    size: str = Query(default="full", pattern="^(full|thumb|small)$"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.photo:
        raise HTTPException(status_code=404, detail="No photo")

    source_path = PHOTO_DIR / Path(user.photo).name
    if not source_path.is_file():
        raise HTTPException(status_code=404, detail="Photo file not found")

    selected_path = source_path
    if size in {"thumb", "small"}:
        selected_path = PHOTO_DIR / f"{source_path.stem}_{size}.jpg"
        if not selected_path.is_file():
            dimensions = {"thumb": (80, 80), "small": (160, 160)}
            try:
                with PILImage.open(source_path) as image:
                    image = image.convert("RGB")
                    image.thumbnail(dimensions[size], PILImage.Resampling.LANCZOS)
                    image.save(selected_path, format="JPEG", quality=82, optimize=True)
            except (UnidentifiedImageError, OSError):
                raise HTTPException(status_code=500, detail="Stored photo could not be processed")

    digest = hashlib.sha256(selected_path.read_bytes()).hexdigest()
    return FileResponse(
        selected_path,
        media_type="image/jpeg",
        headers={
            "Cache-Control": "private, max-age=3600",
            "ETag": f'"{digest}"',
            "Vary": "Authorization",
        },
    )


@router.delete("/users/{user_id}/photo")
def delete_photo(
    user_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    if current.role != "admin" and current.id != user_id:
        raise HTTPException(status_code=403, detail="Can only delete your own photo")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.photo:
        old_path = PHOTO_DIR / Path(user.photo).name
        user.photo = None
        try:
            audit(db, current, "user.photo_delete", "user", user_id)
            db.commit()
        except Exception:
            db.rollback()
            raise HTTPException(status_code=500, detail="Could not delete photo record")
        old_path.unlink(missing_ok=True)
        for variant in ("thumb", "small"):
            (PHOTO_DIR / f"{old_path.stem}_{variant}.jpg").unlink(missing_ok=True)

    return {"message": "Photo deleted"}



# ══════════════════════════════════════════════════════════════════════════════
