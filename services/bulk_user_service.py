from datetime import datetime, timedelta
from io import BytesIO
import os

import openpyxl
from openpyxl.utils.exceptions import InvalidFileException
from sqlalchemy.orm import Session

from core.security import hash_password
from models import User
from services.audit_service import record_audit
from utils.qr import generate_qr_hash, generate_qr_image

MAX_IMPORT_BYTES = 10 * 1024 * 1024
REQUIRED_COLUMNS = {"full_name", "email", "reg_number", "role", "password"}
ALLOWED_ROLES = {"admin", "guard", "student", "staff", "lecturer"}


def import_users_workbook(db: Session, admin: User, content: bytes) -> dict:
    if not content:
        raise ValueError("Workbook is empty")
    if len(content) > MAX_IMPORT_BYTES:
        raise OverflowError("Workbook must not exceed 10 MB")
    try:
        workbook = openpyxl.load_workbook(BytesIO(content), read_only=True, data_only=True)
    except (InvalidFileException, OSError, ValueError) as exc:
        raise ValueError("Uploaded file is not a valid Excel workbook") from exc

    worksheet = workbook.active
    headers = None
    header_row_index = None
    for row_index, row in enumerate(worksheet.iter_rows(min_row=1, max_row=10, values_only=True), start=1):
        candidate = [str(value).strip().lower() if value is not None else "" for value in row]
        if REQUIRED_COLUMNS.issubset(set(candidate)):
            headers = candidate
            header_row_index = row_index
            break
    if headers is None or header_row_index is None:
        workbook.close()
        raise ValueError(f"Missing required columns: {', '.join(sorted(REQUIRED_COLUMNS))}")

    created, skipped, errors, generated_qr_files = [], [], [], []
    try:
        for row in worksheet.iter_rows(min_row=header_row_index + 1, values_only=True):
            if not any(value is not None for value in row):
                continue
            data = {
                headers[index]: str(value).strip() if value is not None else ""
                for index, value in enumerate(row)
                if index < len(headers)
            }
            reg_number = data.get("reg_number", "")
            email = data.get("email", "").lower()
            role = data.get("role", "").lower()
            password = data.get("password", "")
            if not all((data.get("full_name"), reg_number, email, password)):
                skipped.append(reg_number or "unknown")
                continue
            if role not in ALLOWED_ROLES:
                errors.append({"reg": reg_number, "error": "Unsupported role"})
                continue
            if len(password) < 10 or len(password) > 128:
                errors.append({"reg": reg_number, "error": "Password must contain 10 to 128 characters"})
                continue
            duplicate = db.query(User.id).filter((User.reg_number == reg_number) | (User.email == email)).first()
            if duplicate:
                skipped.append(reg_number)
                continue

            qr_code = generate_qr_hash(reg_number)
            qr_path = None
            try:
                with db.begin_nested():
                    user = User(
                        full_name=data["full_name"][:120],
                        email=email,
                        reg_number=reg_number[:60],
                        role=role,
                        password=hash_password(password),
                        qr_code=qr_code,
                        qr_expires=datetime.utcnow() + timedelta(days=180),
                    )
                    db.add(user)
                    db.flush()
                    qr_path = generate_qr_image(qr_code, user.full_name)
                if qr_path:
                    generated_qr_files.append(qr_path)
                created.append(reg_number)
            except Exception:
                if qr_path and os.path.exists(qr_path):
                    os.remove(qr_path)
                errors.append({"reg": reg_number, "error": "Could not create this user record"})

        record_audit(db, admin, "users.bulk_import", detail={"created": len(created), "skipped": len(skipped), "errors": len(errors)})
        db.commit()
    except Exception:
        db.rollback()
        for qr_path in generated_qr_files:
            if os.path.exists(qr_path):
                os.remove(qr_path)
        raise
    finally:
        workbook.close()

    return {"created": len(created), "skipped": len(skipped), "errors": errors[:50], "created_list": created[:20]}


def build_import_template() -> BytesIO:
    workbook = openpyxl.Workbook()
    worksheet = workbook.active
    worksheet.title = "Users"
    worksheet.append(["full_name", "email", "reg_number", "role", "password"])
    worksheet.append(["Amara Diallo", "amara@bugema.ac.ug", "23/BIT/BU/R/0001", "student", ""])
    worksheet.append(["Kevin Otieno", "kotieno@bugema.ac.ug", "LEC/2024/001", "lecturer", ""])
    buffer = BytesIO()
    workbook.save(buffer)
    buffer.seek(0)
    return buffer
