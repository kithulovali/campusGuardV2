from datetime import datetime, timedelta
from io import BytesIO
import io
import os

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from core.dependencies import require_admin
from core.security import hash_password
from db.session import get_db
from models import User
from services.audit_service import record_audit
from utils.qr import generate_qr_hash, generate_qr_image


router = APIRouter()


# ══════════════════════════════════════════════════════════════════════════════
# FEATURE 8 — BULK USER IMPORT
# ══════════════════════════════════════════════════════════════════════════════
@router.post("/users/bulk-import")
async def bulk_import(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    import openpyxl
    from openpyxl.utils.exceptions import InvalidFileException

    max_upload_bytes = 10 * 1024 * 1024
    content_bytes = await file.read(max_upload_bytes + 1)
    await file.close()
    if len(content_bytes) > max_upload_bytes:
        raise HTTPException(status_code=413, detail="Workbook must not exceed 10 MB")
    if not content_bytes:
        raise HTTPException(status_code=400, detail="Workbook is empty")

    try:
        workbook = openpyxl.load_workbook(
            BytesIO(content_bytes),
            read_only=True,
            data_only=True,
        )
    except (InvalidFileException, OSError, ValueError):
        raise HTTPException(status_code=400, detail="Uploaded file is not a valid Excel workbook")

    worksheet = workbook.active
    required = {"full_name", "email", "reg_number", "role", "password"}
    headers = None
    header_row_index = None

    for row_index, row in enumerate(
        worksheet.iter_rows(min_row=1, max_row=10, values_only=True),
        start=1,
    ):
        candidate = [
            str(value).strip().lower() if value is not None else ""
            for value in row
        ]
        if required.issubset(set(candidate)):
            headers = candidate
            header_row_index = row_index
            break

    if headers is None or header_row_index is None:
        workbook.close()
        raise HTTPException(
            status_code=400,
            detail=f"Missing required columns: {', '.join(sorted(required))}",
        )

    created = []
    skipped = []
    errors = []
    generated_qr_files = []
    allowed_roles = {"admin", "guard", "student", "staff", "lecturer"}

    try:
        for row in worksheet.iter_rows(
            min_row=header_row_index + 1,
            values_only=True,
        ):
            if not any(value is not None for value in row):
                continue

            data = {
                headers[index]: str(value).strip() if value is not None else ""
                for index, value in enumerate(row)
                if index < len(headers)
            }
            registration_number = data.get("reg_number", "")
            email = data.get("email", "").lower()
            role = data.get("role", "").lower()
            password = data.get("password", "")

            if not all(
                (
                    data.get("full_name"),
                    registration_number,
                    email,
                    password,
                )
            ):
                skipped.append(registration_number or "unknown")
                continue
            if role not in allowed_roles:
                errors.append({
                    "reg": registration_number,
                    "error": "Unsupported role",
                })
                continue
            if len(password) < 10 or len(password) > 128:
                errors.append({
                    "reg": registration_number,
                    "error": "Password must contain 10 to 128 characters",
                })
                continue
            if db.query(User.id).filter(
                (User.reg_number == registration_number) | (User.email == email)
            ).first():
                skipped.append(registration_number)
                continue

            qr_code = generate_qr_hash(registration_number)
            qr_path = None
            try:
                with db.begin_nested():
                    user = User(
                        full_name=data["full_name"][:120],
                        email=email,
                        reg_number=registration_number[:60],
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
                created.append(registration_number)
            except Exception:
                if qr_path and os.path.exists(qr_path):
                    os.remove(qr_path)
                errors.append({
                    "reg": registration_number,
                    "error": "Could not create this user record",
                })

        audit(
            db,
            admin,
            "users.bulk_import",
            detail={"created": len(created), "skipped": len(skipped), "errors": len(errors)},
        )
        db.commit()
    except Exception:
        db.rollback()
        for qr_path in generated_qr_files:
            if os.path.exists(qr_path):
                os.remove(qr_path)
        raise HTTPException(status_code=500, detail="Bulk import could not be completed")
    finally:
        workbook.close()

    return {
        "created": len(created),
        "skipped": len(skipped),
        "errors": errors[:50],
        "created_list": created[:20],
    }


@router.get("/users/bulk-template")
def download_template(_=Depends(require_admin)):
    import openpyxl
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Users"
    headers = ["full_name","email","reg_number","role","password"]
    ws.append(headers)
    ws.append(["Amara Diallo","amara@bugema.ac.ug","23/BIT/BU/R/0001","student",""])
    ws.append(["Kevin Otieno","kotieno@bugema.ac.ug","LEC/2024/001","lecturer",""])
    buf = io.BytesIO(); wb.save(buf); buf.seek(0)
    return StreamingResponse(buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=campusguard_import_template.xlsx"})

# ══════════════════════════════════════════════════════════════════════════════
