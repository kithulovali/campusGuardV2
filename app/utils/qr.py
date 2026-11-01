import hashlib, os, qrcode
from PIL import Image
from datetime import datetime

QR_DIR = "static/qr_codes"

def generate_qr_hash(reg_number: str) -> str:
    raw = f"{reg_number}-{datetime.utcnow().isoformat()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]

def generate_qr_image(qr_hash: str, user_name: str) -> str:
    os.makedirs(QR_DIR, exist_ok=True)
    path = os.path.join(QR_DIR, f"{qr_hash}.png")
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(qr_hash)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#0D1B2A", back_color="white")
    img.save(path)
    return path
