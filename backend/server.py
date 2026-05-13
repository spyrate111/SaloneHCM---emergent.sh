"""SaloneHCM API entry point — wires routers and middleware."""
import logging
from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from core import client, limiter
from seeders import seed
from storage import init_storage
import scheduler as payroll_scheduler
from routers import (
    auth, employees, payroll, compliance, leave, attendance,
    dashboard, audit, assistant, benefits, talent, analytics, simulator, team,
    documents, company, admin, users, schedules, ministry, public,
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

api = APIRouter(prefix="/api")
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


@api.get("/")
async def root():
    return {"app": "SaloneHCM", "status": "ok", "version": "1.2"}


app.include_router(api)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
