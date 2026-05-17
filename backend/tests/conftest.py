"""Shared pytest helpers — auto-injects TOTP code for the seed superadmin so
the existing test suites keep working under strict 2FA enforcement."""
import os
import pyotp
import requests

# Read the same secret used by the seeder. Falls back to the known dev-only
# default so contributor laptops Just Work without extra env setup; production
# CI must inject its own SUPERADMIN_TOTP_SECRET.
SUPERADMIN_TOTP_SECRET = os.environ.get(
    "SUPERADMIN_TOTP_SECRET",
    "KRSXG5BANFXSAYTBORQXG43LMR2A",
)
SUPERADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@salonehcm.sl").lower()


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
