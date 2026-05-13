"""Shared pytest helpers — auto-injects TOTP code for the seed superadmin so
the existing test suites keep working under strict 2FA enforcement."""
import pyotp
import requests

# Same deterministic secret as `seeders/users.py` — testing-only.
SUPERADMIN_TOTP_SECRET = "KRSXG5BANFXSAYTBORQXG43LMR2A"
SUPERADMIN_EMAIL = "admin@salonehcm.sl"


def totp_now() -> str:
    return pyotp.TOTP(SUPERADMIN_TOTP_SECRET).now()


_orig_post = requests.post


def _patched_post(url, *args, **kwargs):
    """Auto-inject totp_code when logging in as the seed superadmin."""
    try:
        if isinstance(url, str) and url.endswith("/auth/login"):
            json_body = kwargs.get("json")
            if isinstance(json_body, dict) and (json_body.get("email", "").lower() == SUPERADMIN_EMAIL) and "totp_code" not in json_body:
                json_body = {**json_body, "totp_code": totp_now()}
                kwargs["json"] = json_body
    except Exception:
        pass
    return _orig_post(url, *args, **kwargs)


# Install once for the whole pytest session
requests.post = _patched_post
