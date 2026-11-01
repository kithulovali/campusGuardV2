import hashlib
from io import BytesIO
from pathlib import Path
import uuid

from PIL import Image as PILImage, UnidentifiedImageError
from sqlalchemy.orm import Session

from models import User
from services.audit_service import record_audit

PHOTO_DIR = Path(__file__).resolve().parents[1] / "static" / "photos"
MAX_PHOTO_BYTES = 5 * 1024 * 1024
ALLOWED_PHOTO_TYPES = {"image/jpeg", "image/png", "image/webp"}


def save_user_photo(db: Session, user: User, actor: User, content: bytes) -> str:
    if not content:
        raise ValueError("Uploaded image is empty")
    if len(content) > MAX_PHOTO_BYTES:
        raise OverflowError("Photo must not exceed 5 MB")
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
    except (UnidentifiedImageError, OSError, ValueError, PILImage.DecompressionBombError) as exc:
        raise ValueError("Uploaded file is not a valid image") from exc

    previous_photo = user.photo
    user.photo = f"/static/photos/{filename}"
    try:
        record_audit(db, actor, "user.photo_upload", "user", user.id)
        db.commit()
    except Exception:
        db.rollback()
        destination.unlink(missing_ok=True)
        raise
    _delete_photo_files(previous_photo)
    return user.photo


def get_user_photo_path(user: User, size: str = "full") -> Path:
    if not user.photo:
        raise FileNotFoundError("No photo")
    source = PHOTO_DIR / Path(user.photo).name
    if not source.is_file():
        raise FileNotFoundError("Photo file not found")
    if size == "full":
        return source
    dimensions = {"thumb": (80, 80), "small": (160, 160)}
    destination = PHOTO_DIR / f"{source.stem}_{size}.jpg"
    if not destination.is_file():
        try:
            with PILImage.open(source) as image:
                image = image.convert("RGB")
                image.thumbnail(dimensions[size], PILImage.Resampling.LANCZOS)
                image.save(destination, format="JPEG", quality=82, optimize=True)
        except (UnidentifiedImageError, OSError) as exc:
            raise RuntimeError("Stored photo could not be processed") from exc
    return destination


def photo_etag(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def delete_user_photo(db: Session, user: User, actor: User) -> None:
    previous_photo = user.photo
    if not previous_photo:
        return
    user.photo = None
    try:
        record_audit(db, actor, "user.photo_delete", "user", user.id)
        db.commit()
    except Exception:
        db.rollback()
        raise
    _delete_photo_files(previous_photo)


def _delete_photo_files(photo_url: str | None) -> None:
    if not photo_url:
        return
    path = PHOTO_DIR / Path(photo_url).name
    path.unlink(missing_ok=True)
    for variant in ("thumb", "small"):
        (PHOTO_DIR / f"{path.stem}_{variant}.jpg").unlink(missing_ok=True)
