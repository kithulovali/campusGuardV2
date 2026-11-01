import hashlib
from datetime import datetime
from pathlib import Path

import qrcode


QR_DIR = Path(__file__).resolve().parents[1] / "static" / "qr_codes"


def generate_qr_hash(reg_number: str) -> str:
    raw = f"{reg_number}-{datetime.utcnow().isoformat()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def generate_qr_image(qr_hash: str, user_name: str) -> str:
    QR_DIR.mkdir(parents=True, exist_ok=True)
    path = QR_DIR / f"{qr_hash}.png"
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(qr_hash)
    qr.make(fit=True)
    image = qr.make_image(fill_color="#0D1B2A", back_color="white")
    image.save(path)
    return str(path)
