from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.models import User, RefreshToken
from app.schemas.schemas import LoginRequest, TokenResponse, RefreshRequest
from app.core.security import verify_password, create_access_token, create_refresh_token, decode_token
from datetime import datetime, timedelta
from app.core.config import settings

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = (
        db.query(User).filter(User.email == body.username).first() or
        db.query(User).filter(User.reg_number == body.username).first()
    )
    if not user or not verify_password(body.password, user.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if user.status == "inactive":
        raise HTTPException(status_code=403, detail="Account inactive")

    access  = create_access_token({"sub": str(user.id), "role": user.role})
    refresh = create_refresh_token({"sub": str(user.id)})

    rt = RefreshToken(
        user_id=user.id, token=refresh,
        expires_at=datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    )
    db.add(rt); db.commit()

    return {
        "access_token": access,
        "refresh_token": refresh,
        "user": {
            "id": user.id, "full_name": user.full_name,
            "role": user.role, "reg_number": user.reg_number,
            "email": user.email, "status": user.status,
        }
    }

@router.post("/refresh")
def refresh(body: RefreshRequest, db: Session = Depends(get_db)):
    try:
        payload = decode_token(body.refresh_token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    rt = db.query(RefreshToken).filter(
        RefreshToken.token == body.refresh_token,
        RefreshToken.revoked == False
    ).first()
    if not rt:
        raise HTTPException(status_code=401, detail="Token revoked")

    user_id = payload.get("sub")
    access  = create_access_token({"sub": user_id})
    return {"access_token": access}

@router.post("/logout")
def logout(body: RefreshRequest, db: Session = Depends(get_db)):
    rt = db.query(RefreshToken).filter(RefreshToken.token == body.refresh_token).first()
    if rt:
        rt.revoked = True; db.commit()
    return {"message": "Logged out"}
