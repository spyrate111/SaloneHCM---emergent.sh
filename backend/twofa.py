"""TOTP-based 2FA — currently enabled for super-admin role only."""
import base64
import io
from typing import Optional

import pyotp
import qrcode

ISSUER = "SaloneHCM"


def new_secret() -> str:
    return pyotp.random_base32()


def provisioning_uri(secret: str, email: str) -> str:
    return pyotp.totp.TOTP(secret).provisioning_uri(name=email, issuer_name=ISSUER)


def qr_png_b64(uri: str) -> str:
    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode()}"


def verify(secret: str, code: Optional[str]) -> bool:
    if not code or not secret:
        return False
    code = code.replace(" ", "")
    if not code.isdigit() or len(code) != 6:
        return False
    return pyotp.TOTP(secret).verify(code, valid_window=1)
