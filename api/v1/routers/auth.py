from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from db.session import get_db
from schemas.schemas import AccessTokenResponse, LoginRequest, RefreshRequest, RegistrationRequest, TokenResponse
from services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegistrationRequest, db: Session = Depends(get_db)):
    """Create a student account and return authenticated tokens.

    Public registration is restricted to the student role. Staff, guards,
    and administrator accounts must be provisioned by an administrator.
    """
    return AuthService(db).register(
        full_name=payload.full_name,
        email=str(payload.email),
        reg_number=payload.reg_number,
        password=payload.password,
    )


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    return AuthService(db).login(payload.identifier, payload.password)


@router.post("/refresh", response_model=AccessTokenResponse)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    return AuthService(db).refresh(payload.refresh_token)


@router.post("/logout", status_code=204)
def logout(payload: RefreshRequest, db: Session = Depends(get_db)):
    AuthService(db).logout(payload.refresh_token)
