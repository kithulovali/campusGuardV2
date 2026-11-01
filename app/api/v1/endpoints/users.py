from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from typing import List, Optional
import os, shutil
from app.db.session import get_db
from app.models.models import User
from app.schemas.schemas import UserCreate, UserUpdate, UserOut, UserPublic
from app.core.dependencies import require_admin, get_current_user
from app.core.security import hash_password
from app.utils.qr import generate_qr_hash, generate_qr_image
from app.core.config import settings

router = APIRouter(prefix="/users", tags=["Users"])

@router.post("/", response_model=UserOut, status_code=201)
def create_user(payload: UserCreate, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=409, detail="Email already registered")
    if db.query(User).filter(User.reg_number == payload.reg_number).first():
        raise HTTPException(status_code=409, detail="Registration number already exists")
    qr_code = generate_qr_hash(payload.reg_number)
    user = User(
        reg_number=payload.reg_number, first_name=payload.first_name, last_name=payload.last_name,
        role=payload.role, email=payload.email, phone=payload.phone, faculty=payload.faculty,
        department=payload.department, year_of_study=payload.year_of_study, qr_code=qr_code,
        password_hash=hash_password(payload.password) if payload.password else None,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    generate_qr_image(user.qr_code, user.reg_number)
    return user

@router.get("/", response_model=List[UserOut])
def list_users(role: Optional[str]=None, status: Optional[str]=None, skip: int=0, limit: int=50, db: Session=Depends(get_db), _: User=Depends(require_admin)):
    q = db.query(User)
    if role:   q = q.filter(User.role == role)
    if status: q = q.filter(User.status == status)
    return q.offset(skip).limit(limit).all()

@router.get("/search", response_model=List[UserPublic])
def search_users(q: str, db: Session = Depends(get_db)):
    return db.query(User).filter(
        (User.first_name.ilike(f"%{q}%")) | (User.last_name.ilike(f"%{q}%")) | (User.reg_number.ilike(f"%{q}%"))
    ).limit(10).all()

@router.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user

@router.get("/{user_id}", response_model=UserOut)
def get_user(user_id: int, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@router.patch("/{user_id}", response_model=UserOut)
@router.put("/{user_id}", response_model=UserOut)
def update_user(user_id: int, payload: UserUpdate, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(user, field, value)
    db.commit()
    db.refresh(user)
    return user

@router.delete("/{user_id}", status_code=204)
def delete_user(user_id: int, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(user)
    db.commit()

@router.get("/{user_id}/qr-image")
def get_qr_image(user_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.id != user_id and current_user.role not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Access denied")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    path = generate_qr_image(user.qr_code, user.reg_number)
    return {"qr_image_path": path, "qr_code": user.qr_code}

@router.get("/{user_id}/qr")
def get_qr(user_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    path = generate_qr_image(user.qr_code, user.reg_number)
    from fastapi.responses import FileResponse
    if os.path.exists(path):
        return FileResponse(path, media_type="image/png")
    raise HTTPException(status_code=404, detail="QR not generated yet")
