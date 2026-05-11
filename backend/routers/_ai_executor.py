"""AI Assistant — action plan step executor, scoped per tenant."""
import uuid
from core import db, audit, now_utc, iso, tenant_filter, with_tenant
from payroll_engine import run_payroll


async def _leave_decision(step, user: dict, meta_base: dict) -> dict:
    tf = tenant_filter(user)
    res = await db.leave_requests.update_one(
        {"id": step.leave_id, **tf},
        {"$set": {"status": step.decision}},
    )
    if not res.matched_count:
        raise ValueError(f"leave {step.leave_id} not found")
    await audit(f"ai_leave_{step.decision}", f"leave_requests/{step.leave_id}", user, meta_base)
    return {"detail": f"Leave {step.leave_id} {step.decision}"}


async def _payroll_run(step, user: dict, _meta_base: dict) -> dict:
    doc = await run_payroll(step.year, step.month, user, audit_action="ai_payroll_run")
    return {"detail": f"Payroll {doc['period']} run, net SLE {doc['totals']['net']:,.2f}"}


async def _attendance_log(step, user: dict, meta_base: dict) -> dict:
    # Validate employee belongs to user's tenant
    tf = tenant_filter(user)
    emp = await db.employees.find_one({"id": step.employee_id, **tf}, {"_id": 0, "id": 1})
    if not emp:
        raise ValueError(f"employee {step.employee_id} not in your organization")
    doc = with_tenant({
        "id": str(uuid.uuid4()),
        "employee_id": step.employee_id,
        "date": step.date,
        "hours": step.hours,
        "overtime_hours": step.overtime_hours,
        "notes": step.notes or "[AI-logged]",
        "created_at": iso(now_utc()),
    }, user)
    await db.attendance.insert_one(doc)
    await audit("ai_attendance_log", f"attendance/{doc['id']}", user, {**meta_base, "date": step.date})
    return {"detail": f"Logged {step.hours}h on {step.date}"}


async def _leave_create(step, user: dict, meta_base: dict) -> dict:
    tf = tenant_filter(user)
    emp = await db.employees.find_one({"id": step.employee_id, **tf}, {"_id": 0})
    if not emp:
        raise ValueError(f"employee {step.employee_id} not in your organization")
    doc = with_tenant({
        "id": str(uuid.uuid4()),
        "employee_id": step.employee_id,
        "employee_name": f'{emp["first_name"]} {emp["last_name"]}',
        "leave_type": step.leave_type,
        "start_date": step.start_date,
        "end_date": step.end_date,
        "days": step.days,
        "reason": step.reason or "[AI-created]",
        "status": "pending",
        "created_at": iso(now_utc()),
    }, user)
    await db.leave_requests.insert_one(doc)
    await audit("ai_leave_create", f"leave_requests/{doc['id']}", user, meta_base)
    return {"detail": f"Leave request created for {doc['employee_name']}"}


async def _payroll_simulate(step, user: dict, meta_base: dict) -> dict:
    from routers.simulator import _do_simulate, SimIn, SimRule
    rules = [SimRule(**r.model_dump()) for r in step.rules]
    sim_result = await _do_simulate(SimIn(rules=rules), user)
    await audit("ai_payroll_simulate", "payroll/simulate", user, {
        **meta_base,
        "annualized_delta": sim_result["annualized_delta_employer_cost"],
        "affected": sim_result["affected_employees_count"],
    })
    delta = sim_result["delta"]["employer_total_cost"]
    return {
        "detail": f"Δ employer cost SLE {delta:,.2f}/mo · annualized SLE {sim_result['annualized_delta_employer_cost']:,.2f}",
        "simulation": sim_result,
    }


async def _scenario_apply(step, user: dict, _meta_base: dict) -> dict:
    from routers.simulator import _do_apply_scenario
    result = await _do_apply_scenario(step.scenario_id, user)
    return {
        "detail": f"Applied '{result['scenario_title']}' — {result['employees_changed']} employee(s) updated",
        "scenario_apply": result,
    }


HANDLERS = {
    "leave_decision": _leave_decision,
    "payroll_run": _payroll_run,
    "attendance_log": _attendance_log,
    "leave_create": _leave_create,
    "payroll_simulate": _payroll_simulate,
    "scenario_apply": _scenario_apply,
}


async def exec_step(step, user: dict, plan_title: str) -> dict:
    handler = HANDLERS.get(step.type)
    if not handler:
        raise ValueError(f"Unknown step type: {step.type}")
    return await handler(step, user, {"plan_title": plan_title})
