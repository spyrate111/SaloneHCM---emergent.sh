"""SaloneHCM API entry point — wires routers and middleware."""
import logging
import os
from fastapi import FastAPI, APIRouter, Depends
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from core import client, limiter, csrf_protect
from seeders import seed
from storage import init_storage
import scheduler as payroll_scheduler
from routers import (
    auth, employees, payroll, compliance, leave, attendance,
    dashboard, audit, assistant, benefits, talent, analytics, simulator, team,
    documents, company, admin, users, schedules, ministry, public, integrations,
    push, performance, civil_service, ifmis, establishment, loans, billing, stripe_webhook,
    sector_presets, promotion,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("salonehcm")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await seed()
    try:
        init_storage()
    except Exception as e:
        logger.warning("Object storage init failed (uploads will fail until env is set): %s", e)
    try:
        payroll_scheduler.start()
    except Exception as e:
        logger.warning("Payroll scheduler failed to start: %s", e)
    yield
    payroll_scheduler.stop()
    client.close()


app = FastAPI(title="SaloneHCM API", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

api = APIRouter(prefix="/api", dependencies=[Depends(csrf_protect)])
api.include_router(auth.router)
api.include_router(employees.router)
api.include_router(payroll.router)
api.include_router(compliance.router)
api.include_router(leave.router)
api.include_router(attendance.router)
api.include_router(dashboard.router)
api.include_router(audit.router)
api.include_router(assistant.router)
api.include_router(benefits.router)
api.include_router(talent.router)
api.include_router(analytics.router)
api.include_router(simulator.router)
api.include_router(team.router)
api.include_router(documents.router)
api.include_router(company.router)
api.include_router(admin.router)
api.include_router(users.router)
api.include_router(schedules.router)
api.include_router(ministry.router)
api.include_router(public.router)
api.include_router(integrations.router)
api.include_router(push.router)
api.include_router(performance.router)
api.include_router(civil_service.router)
api.include_router(ifmis.router)
api.include_router(establishment.router)
api.include_router(loans.router)
api.include_router(billing.router)
api.include_router(stripe_webhook.router)
api.include_router(sector_presets.router)
api.include_router(promotion.router)


@api.get("/")
async def root():
    return {"app": "SaloneHCM", "status": "ok", "version": "1.2"}


app.include_router(api)

# CORS — when cookies are used, browsers reject Access-Control-Allow-Origin='*'.
#
# Production cutover: set `CORS_ALLOWED_ORIGINS` to a comma-separated allowlist
# of explicit https origins (e.g. https://app.salonehcm.gov.sl,https://hcm.mof.gov.sl)
# and unset `CORS_ALLOW_PREVIEW` to disable the wildcard preview regex.
#
# When `CORS_ALLOWED_ORIGINS` is unset we fall back to the preview-host regex
# (any *.preview.emergentagent.com) + localhost. This keeps preview/dev working
# but is NOT safe for prod.
_explicit = [o.strip().rstrip("/") for o in os.environ.get("CORS_ALLOWED_ORIGINS", "").split(",") if o.strip()]
_legacy_frontend_url = os.environ.get("FRONTEND_URL", "").strip().rstrip("/")
if _legacy_frontend_url and _legacy_frontend_url not in _explicit:
    _explicit.append(_legacy_frontend_url)
_allow_preview = os.environ.get("CORS_ALLOW_PREVIEW", "1") not in ("0", "false", "False", "")
_preview_regex = r"https://[^/]+\.preview\.emergentagent\.com" if _allow_preview else None

# When neither an explicit allowlist nor the preview regex is configured, fall
# back to localhost-only so the server still boots in CI/dev.
_allow_origins = _explicit or ["http://localhost:3000", "http://127.0.0.1:3000"]

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=_preview_regex,
    allow_origins=_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-CSRF-Token"],
)
logging.getLogger("salonehcm").info(
    "CORS configured: explicit=%s preview_regex=%s",
    _allow_origins, bool(_preview_regex),
)
