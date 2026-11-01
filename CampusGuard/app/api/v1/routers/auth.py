from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.schemas import (
    AccessTokenResponse, LoginRequest, RefreshRequest, TokenResponse,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    result = AuthService(db).login(payload.username, payload.password)
    return {
        "access_token": result["access_token"],
        "refresh_token": result["refresh_token"],
        "user": result["user"],
    }


@router.post("/refresh", response_model=AccessTokenResponse)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    return {"access_token": AuthService(db).refresh(payload.refresh_token)}


@router.post("/logout", status_code=204)
def logout(payload: RefreshRequest, db: Session = Depends(get_db)):
    AuthService(db).logout(payload.refresh_token)
