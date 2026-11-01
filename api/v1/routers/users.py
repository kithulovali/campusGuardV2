from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from core.dependencies import get_current_user, require_admin
from db.session import get_db
from models import User
from repositories.user_repository import UserRepository
from schemas.schemas import UserCreate, UserOut, UserPublic, UserUpdate
from services.user_service import UserService

router = APIRouter(prefix="/users", tags=["Users"])


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, db: Session = Depends(get_db),
                _: User = Depends(require_admin)):
    return UserService(db).create(payload)


@router.get("", response_model=list[UserOut])
def list_users(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    role: str | None = None,
    user_status: str | None = Query(None, alias="status"),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    return UserRepository(db).list(offset=offset, limit=limit, role=role, status=user_status)


@router.get("/search", response_model=list[UserPublic])
def search_users(
    q: str = Query(min_length=2, max_length=100),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return UserRepository(db).search(q)


@router.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.get("/{user_id}", response_model=UserOut)
def get_user(user_id: int, db: Session = Depends(get_db),
             _: User = Depends(require_admin)):
    return UserService(db).get(user_id)


@router.patch("/{user_id}", response_model=UserOut)
def update_user(user_id: int, payload: UserUpdate, db: Session = Depends(get_db),
                _: User = Depends(require_admin)):
    return UserService(db).update(user_id, payload.model_dump(exclude_unset=True))


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: int, db: Session = Depends(get_db),
                _: User = Depends(require_admin)):
    UserService(db).delete(user_id)
