from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from core.dependencies import get_current_user
from db.session import get_db
from models import User
from services.photo_service import ALLOWED_PHOTO_TYPES, MAX_PHOTO_BYTES, delete_user_photo, get_user_photo_path, photo_etag, save_user_photo

router = APIRouter(tags=["Photos & Profiles"])


def _authorize_photo_change(current: User, user_id: int) -> None:
    if current.role != "admin" and current.id != user_id:
        raise HTTPException(status_code=403, detail="Can only manage your own photo")


@router.post("/users/{user_id}/photo")
async def upload_photo(user_id: int, file: UploadFile = File(...), db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    _authorize_photo_change(current, user_id)
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if file.content_type not in ALLOWED_PHOTO_TYPES:
        raise HTTPException(status_code=415, detail="Only JPEG, PNG, and WebP images are accepted")
    content = await file.read(MAX_PHOTO_BYTES + 1)
    await file.close()
    try:
        photo_url = save_user_photo(db, user, current, content)
    except OverflowError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except ValueError as exc:
        status_code = 400 if str(exc) != "Uploaded file is empty" else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Could not save photo record") from exc
    return {"photo_url": photo_url}


@router.get("/users/{user_id}/photo")
def get_photo(user_id: int, size: str = Query(default="full", pattern="^(full|thumb|small)$"), db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="No photo")
    try:
        path = get_user_photo_path(user, size)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return FileResponse(
        path,
        media_type="image/jpeg",
        headers={"Cache-Control": "private, max-age=3600", "ETag": f'"{photo_etag(path)}"', "Vary": "Authorization"},
    )


@router.delete("/users/{user_id}/photo")
def delete_photo(user_id: int, db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    _authorize_photo_change(current, user_id)
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    try:
        delete_user_photo(db, user, current)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Could not delete photo record") from exc
    return {"message": "Photo deleted"}
