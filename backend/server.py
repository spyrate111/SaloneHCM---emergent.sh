from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import os
import uuid
import logging
import bcrypt
import jwt
from datetime import datetime, timezone, timedelta, date
from typing import List, Optional, Literal

from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, EmailStr

# ---- DB ----
mongo_url = os.environ["MONGO_URL"]
db_name = os.environ["DB_NAME"]
client = AsyncIOMotorClient(mongo_url)
db = client[db_name]

JWT_ALGORITHM = "HS256"
JWT_SECRET = os.environ["JWT_SECRET"]

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("salonehcm")

app = FastAPI(title="SaloneHCM API")
api = APIRouter(prefix="/api")


# ---------- Helpers ----------
def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def hash_password(p: str) -> str:
    return bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()


def verify_password(p: str, h: str) -> bool:
    try:
        return bcrypt.checkpw(p.encode(), h.encode())
    except Exception:
        return False


def make_access(uid: str, email: str, role: str) -> str:
    payload = {
        "sub": uid,
        "email": email,
        "role": role,
        "type": "access",
        "exp": now_utc() + timedelta(hours=12),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def set_auth_cookie(resp: Response, token: str):
    resp.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=True,
        samesite="none",
        max_age=43200,
        path="/",
    )


async def get_current_user(request: Request) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        ah = request.headers.get("Authorization", "")
        if ah.startswith("Bearer "):
            token = ah[7:]
    if not token:
        raise HTTPException(401, "Not authenticated")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")
    user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0, "password_hash": 0})
    if not user:
        raise HTTPException(401, "User not found")
    return user


async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(403, "Admin only")
    return user


# ---------- Models ----------
class LoginIn(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: str
    email: str
    name: str
    role: str
    employee_id: Optional[str] = None


class EmployeeIn(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    phone: Optional[str] = ""
    job_title: str
    department: str
    location: str = "Freetown"
    employment_type: Literal["Full-time", "Part-time", "Contract", "Intern"] = "Full-time"
    basic_salary_sle: float
    allowances_sle: float = 0
    nassit_no: Optional[str] = ""
    tin: Optional[str] = ""
    hire_date: str  # YYYY-MM-DD
    status: Literal["active", "on_leave", "terminated"] = "active"


class EmployeeOut(EmployeeIn):
    id: str
    created_at: str


class LeaveIn(BaseModel):
    employee_id: str
    leave_type: Literal["annual", "sick", "maternity", "paternity", "unpaid"]
    start_date: str
    end_date: str
    reason: Optional[str] = ""


class LeaveDecision(BaseModel):
    status: Literal["approved", "rejected"]


class TimeEntryIn(BaseModel):
    employee_id: str
    date: str
    hours: float
    overtime_hours: float = 0
    notes: Optional[str] = ""


class PayrollRunIn(BaseModel):
    period_month: int  # 1-12
    period_year: int


class AssistantMessageIn(BaseModel):
    session_id: Optional[str] = None
    message: str


# ---------- Sierra Leone Payroll Engine ----------
# NRA PAYE (monthly, SLE) - approximated bands
PAYE_BANDS = [
    (800, 0.0),
    (2200, 0.15),
    (3600, 0.20),
    (5000, 0.25),
    (7500, 0.30),
    (float("inf"), 0.35),
]
# NASSIT
NASSIT_EMPLOYEE = 0.05
NASSIT_EMPLOYER = 0.10


def calc_paye(taxable: float) -> float:
    if taxable <= 0:
        return 0.0
    tax = 0.0
    prev = 0.0
    for upper, rate in PAYE_BANDS:
        slab = min(taxable, upper) - prev
        if slab > 0:
            tax += slab * rate
        if taxable <= upper:
            break
        prev = upper
    return round(tax, 2)


def calc_payslip(emp: dict) -> dict:
    basic = float(emp.get("basic_salary_sle", 0))
    allow = float(emp.get("allowances_sle", 0))
    gross = basic + allow
    nassit_emp = round(basic * NASSIT_EMPLOYEE, 2)
    nassit_er = round(basic * NASSIT_EMPLOYER, 2)
    taxable = max(0.0, gross - nassit_emp)
    paye = calc_paye(taxable)
    net = round(gross - nassit_emp - paye, 2)
    return {
        "employee_id": emp["id"],
        "employee_name": f'{emp["first_name"]} {emp["last_name"]}',
        "basic": basic,
        "allowances": allow,
        "gross": round(gross, 2),
        "nassit_employee": nassit_emp,
        "nassit_employer": nassit_er,
        "paye": paye,
        "net": net,
    }


# ---------- Auth Endpoints ----------
@api.post("/auth/login")
async def login(body: LoginIn, response: Response):
    email = body.email.lower().strip()
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(401, "Invalid email or password")
    token = make_access(user["id"], user["email"], user["role"])
    set_auth_cookie(response, token)
    return {
        "id": user["id"],
        "email": user["email"],
        "name": user["name"],
        "role": user["role"],
        "employee_id": user.get("employee_id"),
        "token": token,
    }


@api.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie("access_token", path="/")
    return {"ok": True}


@api.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    return user


# ---------- Employees ----------
@api.get("/employees")
async def list_employees(user: dict = Depends(get_current_user)):
    rows = await db.employees.find({}, {"_id": 0}).sort("created_at", -1).to_list(2000)
    return rows


@api.post("/employees")
async def create_employee(body: EmployeeIn, _: dict = Depends(require_admin)):
    eid = str(uuid.uuid4())
    doc = {**body.model_dump(), "id": eid, "created_at": iso(now_utc())}
    await db.employees.insert_one(doc)
    doc.pop("_id", None)
    return doc


@api.get("/employees/{eid}")
async def get_employee(eid: str, _: dict = Depends(get_current_user)):
    e = await db.employees.find_one({"id": eid}, {"_id": 0})
    if not e:
        raise HTTPException(404, "Not found")
    return e


@api.put("/employees/{eid}")
async def update_employee(eid: str, body: EmployeeIn, _: dict = Depends(require_admin)):
    res = await db.employees.update_one({"id": eid}, {"$set": body.model_dump()})
    if not res.matched_count:
        raise HTTPException(404, "Not found")
    e = await db.employees.find_one({"id": eid}, {"_id": 0})
    return e


@api.delete("/employees/{eid}")
async def delete_employee(eid: str, _: dict = Depends(require_admin)):
    await db.employees.delete_one({"id": eid})
    return {"ok": True}


# ---------- Payroll ----------
@api.post("/payroll/preview")
async def preview_payroll(_: dict = Depends(require_admin)):
    emps = await db.employees.find({"status": "active"}, {"_id": 0}).to_list(2000)
    slips = [calc_payslip(e) for e in emps]
    totals = {
        "employee_count": len(slips),
        "gross": round(sum(s["gross"] for s in slips), 2),
        "nassit_employee": round(sum(s["nassit_employee"] for s in slips), 2),
        "nassit_employer": round(sum(s["nassit_employer"] for s in slips), 2),
        "paye": round(sum(s["paye"] for s in slips), 2),
        "net": round(sum(s["net"] for s in slips), 2),
    }
    return {"slips": slips, "totals": totals}


@api.post("/payroll/run")
async def run_payroll(body: PayrollRunIn, _: dict = Depends(require_admin)):
    emps = await db.employees.find({"status": "active"}, {"_id": 0}).to_list(2000)
    slips = [calc_payslip(e) for e in emps]
    rid = str(uuid.uuid4())
    period = f"{body.period_year}-{body.period_month:02d}"
    doc = {
        "id": rid,
        "period": period,
        "period_year": body.period_year,
        "period_month": body.period_month,
        "slips": slips,
        "totals": {
            "employee_count": len(slips),
            "gross": round(sum(s["gross"] for s in slips), 2),
            "nassit_employee": round(sum(s["nassit_employee"] for s in slips), 2),
            "nassit_employer": round(sum(s["nassit_employer"] for s in slips), 2),
            "paye": round(sum(s["paye"] for s in slips), 2),
            "net": round(sum(s["net"] for s in slips), 2),
        },
        "status": "completed",
        "created_at": iso(now_utc()),
    }
    await db.payroll_runs.insert_one(doc)
    doc.pop("_id", None)
    return doc


@api.get("/payroll/runs")
async def list_runs(_: dict = Depends(get_current_user)):
    rows = await db.payroll_runs.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
    return rows


@api.get("/payroll/runs/{rid}")
async def get_run(rid: str, _: dict = Depends(get_current_user)):
    r = await db.payroll_runs.find_one({"id": rid}, {"_id": 0})
    if not r:
        raise HTTPException(404, "Not found")
    return r


@api.get("/payroll/my-payslip")
async def my_payslip(user: dict = Depends(get_current_user)):
    eid = user.get("employee_id")
    if not eid:
        return {"slip": None}
    e = await db.employees.find_one({"id": eid}, {"_id": 0})
    if not e:
        return {"slip": None}
    return {"slip": calc_payslip(e)}


# ---------- Compliance ----------
@api.get("/compliance/summary")
async def compliance_summary(_: dict = Depends(get_current_user)):
    runs = await db.payroll_runs.find({}, {"_id": 0}).sort("created_at", -1).to_list(50)
    total_paye = sum(r["totals"]["paye"] for r in runs)
    total_nassit = sum(r["totals"]["nassit_employee"] + r["totals"]["nassit_employer"] for r in runs)
    return {
        "runs_count": len(runs),
        "ytd_paye_sle": round(total_paye, 2),
        "ytd_nassit_sle": round(total_nassit, 2),
        "next_filing": "NRA PAYE — 15th of next month",
        "regs": {"paye_bands": PAYE_BANDS[:-1], "nassit_employee": NASSIT_EMPLOYEE, "nassit_employer": NASSIT_EMPLOYER},
    }


@api.get("/compliance/nra-export/{rid}")
async def nra_export(rid: str, _: dict = Depends(require_admin)):
    r = await db.payroll_runs.find_one({"id": rid}, {"_id": 0})
    if not r:
        raise HTTPException(404, "Not found")
    rows = [
        {
            "employee": s["employee_name"],
            "gross_sle": s["gross"],
            "paye_sle": s["paye"],
            "nassit_employee_sle": s["nassit_employee"],
            "nassit_employer_sle": s["nassit_employer"],
            "net_sle": s["net"],
        }
        for s in r["slips"]
    ]
    return {"period": r["period"], "rows": rows, "totals": r["totals"]}


# ---------- Leave ----------
@api.get("/leave")
async def list_leaves(user: dict = Depends(get_current_user)):
    q = {} if user["role"] == "admin" else {"employee_id": user.get("employee_id")}
    rows = await db.leave_requests.find(q, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return rows


@api.post("/leave")
async def create_leave(body: LeaveIn, user: dict = Depends(get_current_user)):
    eid = body.employee_id if user["role"] == "admin" else user.get("employee_id")
    if not eid:
        raise HTTPException(400, "employee_id required")
    emp = await db.employees.find_one({"id": eid}, {"_id": 0})
    days = (datetime.fromisoformat(body.end_date) - datetime.fromisoformat(body.start_date)).days + 1
    doc = {
        "id": str(uuid.uuid4()),
        "employee_id": eid,
        "employee_name": f'{emp["first_name"]} {emp["last_name"]}' if emp else "Unknown",
        "leave_type": body.leave_type,
        "start_date": body.start_date,
        "end_date": body.end_date,
        "days": max(1, days),
        "reason": body.reason,
        "status": "pending",
        "created_at": iso(now_utc()),
    }
    await db.leave_requests.insert_one(doc)
    doc.pop("_id", None)
    return doc


@api.put("/leave/{lid}/decision")
async def decide_leave(lid: str, body: LeaveDecision, _: dict = Depends(require_admin)):
    res = await db.leave_requests.update_one({"id": lid}, {"$set": {"status": body.status}})
    if not res.matched_count:
        raise HTTPException(404, "Not found")
    return {"ok": True, "status": body.status}


# ---------- Time & Attendance ----------
@api.get("/attendance")
async def list_attendance(user: dict = Depends(get_current_user)):
    q = {} if user["role"] == "admin" else {"employee_id": user.get("employee_id")}
    rows = await db.attendance.find(q, {"_id": 0}).sort("date", -1).to_list(1000)
    return rows


@api.post("/attendance")
async def add_attendance(body: TimeEntryIn, user: dict = Depends(get_current_user)):
    eid = body.employee_id if user["role"] == "admin" else user.get("employee_id")
    if not eid:
        raise HTTPException(400, "employee_id required")
    doc = {
        "id": str(uuid.uuid4()),
        "employee_id": eid,
        "date": body.date,
        "hours": body.hours,
        "overtime_hours": body.overtime_hours,
        "notes": body.notes,
        "created_at": iso(now_utc()),
    }
    await db.attendance.insert_one(doc)
    doc.pop("_id", None)
    return doc


# ---------- Dashboard ----------
@api.get("/dashboard/overview")
async def dashboard(_: dict = Depends(get_current_user)):
    employees = await db.employees.find({}, {"_id": 0}).to_list(2000)
    active = [e for e in employees if e.get("status") == "active"]
    payroll_cost = sum(float(e.get("basic_salary_sle", 0)) + float(e.get("allowances_sle", 0)) for e in active)
    runs = await db.payroll_runs.find({}, {"_id": 0}).sort("created_at", -1).to_list(12)
    pending_leaves = await db.leave_requests.count_documents({"status": "pending"})
    dept_counts = {}
    for e in active:
        dept_counts[e["department"]] = dept_counts.get(e["department"], 0) + 1
    return {
        "headcount": len(active),
        "total_employees": len(employees),
        "monthly_payroll_sle": round(payroll_cost, 2),
        "pending_leaves": pending_leaves,
        "last_run": runs[0] if runs else None,
        "runs_history": [
            {"period": r["period"], "net": r["totals"]["net"], "gross": r["totals"]["gross"]}
            for r in reversed(runs)
        ],
        "departments": [{"name": k, "count": v} for k, v in dept_counts.items()],
    }


# ---------- AI Assistant ----------
@api.post("/assistant/chat")
async def assistant_chat(body: AssistantMessageIn, user: dict = Depends(get_current_user)):
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
    except Exception as e:
        raise HTTPException(500, f"LLM lib unavailable: {e}")

    sid = body.session_id or str(uuid.uuid4())
    sys_msg = (
        "You are SaloneHCM Assistant — an expert on Sierra Leone HR, labor law (Employment Act 2023), "
        "NRA PAYE tax bands, NASSIT contributions (employee 5%, employer 10% of basic), and payroll best practices. "
        "Answer in clear, concise tone. Use Sierra Leonean Leone (SLE) currency. When asked about payroll, "
        "explain the calculation steps. Keep replies under 200 words unless detail is requested."
    )
    chat = LlmChat(
        api_key=os.environ["EMERGENT_LLM_KEY"],
        session_id=sid,
        system_message=sys_msg,
    ).with_model("anthropic", "claude-sonnet-4-5-20250929")

    # Load prior history
    history = await db.assistant_messages.find({"session_id": sid}, {"_id": 0}).sort("ts", 1).to_list(50)
    # Save user msg
    await db.assistant_messages.insert_one({
        "id": str(uuid.uuid4()),
        "session_id": sid,
        "role": "user",
        "content": body.message,
        "user_id": user["id"],
        "ts": iso(now_utc()),
    })

    try:
        reply = await chat.send_message(UserMessage(text=body.message))
    except Exception as e:
        logger.exception("LLM error")
        raise HTTPException(502, f"AI error: {e}")

    await db.assistant_messages.insert_one({
        "id": str(uuid.uuid4()),
        "session_id": sid,
        "role": "assistant",
        "content": reply,
        "user_id": user["id"],
        "ts": iso(now_utc()),
    })
    return {"session_id": sid, "reply": reply}


@api.get("/assistant/history/{sid}")
async def assistant_history(sid: str, _: dict = Depends(get_current_user)):
    rows = await db.assistant_messages.find({"session_id": sid}, {"_id": 0}).sort("ts", 1).to_list(200)
    return rows


# ---------- Health ----------
@api.get("/")
async def root():
    return {"app": "SaloneHCM", "status": "ok", "version": "1.0"}


# ---------- Seed ----------
SEED_EMPLOYEES = [
    ("Aminata", "Kamara", "Senior HR Manager", "Human Resources", 8500, 1200),
    ("Mohamed", "Sesay", "Software Engineer", "Engineering", 6200, 800),
    ("Fatmata", "Bangura", "Accountant", "Finance", 4800, 600),
    ("Ibrahim", "Conteh", "Operations Lead", "Operations", 5500, 700),
    ("Hawa", "Turay", "Marketing Specialist", "Marketing", 3800, 500),
    ("Abdul", "Jalloh", "Sales Executive", "Sales", 3200, 1000),
    ("Isatu", "Mansaray", "Customer Support", "Support", 2400, 300),
    ("Sahr", "Koroma", "DevOps Engineer", "Engineering", 7200, 900),
    ("Mariama", "Fofanah", "Junior Accountant", "Finance", 2800, 400),
    ("Alhaji", "Bah", "Office Administrator", "Operations", 2100, 250),
]


async def seed():
    await db.users.create_index("email", unique=True)
    await db.employees.create_index("email", unique=True)

    admin_email = os.environ["ADMIN_EMAIL"].lower()
    admin_password = os.environ["ADMIN_PASSWORD"]
    existing = await db.users.find_one({"email": admin_email})
    if not existing:
        await db.users.insert_one({
            "id": str(uuid.uuid4()),
            "email": admin_email,
            "name": "System Administrator",
            "role": "admin",
            "password_hash": hash_password(admin_password),
            "created_at": iso(now_utc()),
        })
        logger.info(f"Seeded admin: {admin_email}")
    elif not verify_password(admin_password, existing["password_hash"]):
        await db.users.update_one(
            {"email": admin_email},
            {"$set": {"password_hash": hash_password(admin_password)}},
        )

    if await db.employees.count_documents({}) == 0:
        for fn, ln, title, dept, basic, allow in SEED_EMPLOYEES:
            eid = str(uuid.uuid4())
            email = f"{fn.lower()}.{ln.lower()}@salonehcm.sl"
            await db.employees.insert_one({
                "id": eid,
                "first_name": fn,
                "last_name": ln,
                "email": email,
                "phone": "+232 76 000 000",
                "job_title": title,
                "department": dept,
                "location": "Freetown",
                "employment_type": "Full-time",
                "basic_salary_sle": basic,
                "allowances_sle": allow,
                "nassit_no": f"NS{eid[:8].upper()}",
                "tin": f"TIN{eid[:6].upper()}",
                "hire_date": "2024-01-15",
                "status": "active",
                "created_at": iso(now_utc()),
            })
            # also create employee user account (default password = employee@2026)
            await db.users.insert_one({
                "id": str(uuid.uuid4()),
                "email": email,
                "name": f"{fn} {ln}",
                "role": "employee",
                "employee_id": eid,
                "password_hash": hash_password("Employee@2026"),
                "created_at": iso(now_utc()),
            })
        logger.info("Seeded employees and employee accounts")


@app.on_event("startup")
async def on_start():
    await seed()


@app.on_event("shutdown")
async def on_shutdown():
    client.close()


# ---------- App wiring ----------
app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,  # using Bearer token primarily
    allow_methods=["*"],
    allow_headers=["*"],
)
