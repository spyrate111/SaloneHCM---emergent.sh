"""All Pydantic request/response models."""
from typing import Optional, Literal, List, Union, Annotated
from pydantic import BaseModel, EmailStr, Field


# ---------- Auth ----------
class LoginIn(BaseModel):
    email: EmailStr
    password: str


# ---------- Employees ----------
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
    bank_name: Optional[str] = "Sierra Leone Commercial Bank"
    bank_account: Optional[str] = ""
    hire_date: str
    status: Literal["active", "on_leave", "terminated"] = "active"
    manager_id: Optional[str] = None
    is_manager: bool = False


# ---------- Leave ----------
class LeaveIn(BaseModel):
    employee_id: str
    leave_type: Literal["annual", "sick", "maternity", "paternity", "unpaid"]
    start_date: str
    end_date: str
    reason: Optional[str] = ""


class LeaveDecision(BaseModel):
    status: Literal["approved", "rejected"]


# ---------- Attendance ----------
class TimeEntryIn(BaseModel):
    employee_id: str
    date: str
    hours: float
    overtime_hours: float = 0
    notes: Optional[str] = ""


# ---------- Payroll ----------
class PayrollRunIn(BaseModel):
    period_month: int = Field(..., ge=1, le=12)
    period_year: int = Field(..., ge=2020, le=2100)


# ---------- AI Assistant ----------
class AssistantMessageIn(BaseModel):
    session_id: Optional[str] = None
    message: str
    include_context: bool = False
    action_mode: bool = False


# Discriminated union for action plan steps — strong validation
class _LeaveDecisionStep(BaseModel):
    type: Literal["leave_decision"]
    leave_id: str
    decision: Literal["approved", "rejected"]


class _PayrollRunStep(BaseModel):
    type: Literal["payroll_run"]
    year: int = Field(..., ge=2020, le=2100)
    month: int = Field(..., ge=1, le=12)


class _AttendanceLogStep(BaseModel):
    type: Literal["attendance_log"]
    employee_id: str
    date: str
    hours: float
    overtime_hours: float = 0
    notes: Optional[str] = None


class _LeaveCreateStep(BaseModel):
    type: Literal["leave_create"]
    employee_id: str
    leave_type: Literal["annual", "sick", "maternity", "paternity", "unpaid"] = "annual"
    start_date: str
    end_date: str
    days: int = 1
    reason: Optional[str] = None


class _SimRule(BaseModel):
    name: Optional[str] = None
    target: Literal["all", "department", "employee"] = "all"
    department: Optional[str] = None
    employee_id: Optional[str] = None
    basic_pct_change: float = 0
    basic_flat_add: float = 0
    allowances_pct_change: float = 0
    allowances_flat_add: float = 0


class _PayrollSimulateStep(BaseModel):
    type: Literal["payroll_simulate"]
    title: Optional[str] = None
    rules: List[_SimRule] = Field(..., min_length=1, max_length=20)


class _ScenarioApplyStep(BaseModel):
    type: Literal["scenario_apply"]
    scenario_id: str


PlanStep = Annotated[
    Union[_LeaveDecisionStep, _PayrollRunStep, _AttendanceLogStep, _LeaveCreateStep,
          _PayrollSimulateStep, _ScenarioApplyStep],
    Field(discriminator="type"),
]


class ActionPlan(BaseModel):
    title: str = "AI action plan"
    rationale: str = ""
    steps: List[PlanStep] = Field(..., min_length=1, max_length=50)


class ActionPlanIn(BaseModel):
    plan: ActionPlan
    session_id: Optional[str] = None
