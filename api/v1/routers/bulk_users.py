from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from core.dependencies import require_admin
from db.session import get_db
from models import User
from services.bulk_user_service import MAX_IMPORT_BYTES, build_import_template, import_users_workbook

router = APIRouter(tags=["Administration"])


@router.post("/users/bulk-import")
async def bulk_import(file: UploadFile = File(...), db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    content = await file.read(MAX_IMPORT_BYTES + 1)
    await file.close()
    try:
        return import_users_workbook(db, admin, content)
    except OverflowError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Bulk import could not be completed") from exc


@router.get("/users/bulk-template")
def download_template(_=Depends(require_admin)):
    buffer = build_import_template()
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=campusguard_import_template.xlsx"},
    )
