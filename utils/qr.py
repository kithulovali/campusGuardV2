import secrets
from pathlib import Path

import qrcode


QR_DIR = Path(__file__).resolve().parents[1] / "static" / "qr_codes"


def generate_qr_hash(reg_number: str | None = None) -> str:
    """Generate an unpredictable QR bearer token.

    The registration number is accepted for backwards-compatible callers but
    is deliberately not used as entropy because registration numbers are
    guessable identifiers.
    """
    return secrets.token_urlsafe(32)


def generate_qr_image(qr_hash: str, user_name: str) -> str:
    QR_DIR.mkdir(parents=True, exist_ok=True)
    path = QR_DIR / f"{qr_hash}.png"
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(qr_hash)
    qr.make(fit=True)
    image = qr.make_image(fill_color="#0D1B2A", back_color="white")
    image.save(path)
    return str(path)
