"""AI Assistant: chat (with optional context + action mode), context preview, history, action plan execute."""
import os
import re
import json
import uuid
import logging

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import ValidationError

from core import db, get_current_user, require_admin, audit, now_utc, iso, limiter
from models import AssistantMessageIn, ActionPlanIn, ActionPlan
from payroll_engine import run_payroll

logger = logging.getLogger("salonehcm.assistant")
router = APIRouter(prefix="/assistant", tags=["assistant"])


async def _build_company_context() -> str:
    employees = await db.employees.find({}, {"_id": 0}).to_list(2000)
    runs = await db.payroll_runs.find({}, {"_id": 0}).sort("created_at", -1).to_list(3)
    audits = await db.audit_logs.find({}, {"_id": 0}).sort("ts", -1).to_list(50)
    leaves = await db.leave_requests.find({}, {"_id": 0}).sort("created_at", -1).to_list(100)
    attendance = await db.attendance.find({}, {"_id": 0}).sort("date", -1).to_list(100)

    lines = ["=== SALONEHCM COMPANY DATA SNAPSHOT ===", f"Total employees: {len(employees)}"]
    dept = {}
    for e in employees:
        dept[e["department"]] = dept.get(e["department"], 0) + 1
    lines.append("Departments: " + ", ".join(f"{k}({v})" for k, v in dept.items()))

    lines.append("\n--- EMPLOYEES (full) ---")
    for e in employees:
        lines.append(
            f"- id={e['id']} | {e['first_name']} {e['last_name']} | {e['job_title']} | {e['department']} | "
            f"basic SLE {e['basic_salary_sle']:.2f} + allow {e['allowances_sle']:.2f} | status {e['status']}"
        )

    lines.append("\n--- RECENT PAYROLL RUNS ---")
    for r in runs:
        t = r["totals"]
        lines.append(
            f"Run id={r['id']} period={r['period']} | gross SLE {t['gross']:.2f} | PAYE {t['paye']:.2f} | "
            f"NASSIT(emp+er) {t['nassit_employee'] + t['nassit_employer']:.2f} | net {t['net']:.2f} | "
            f"{t['employee_count']} employees"
        )
        for s in r["slips"]:
            lines.append(f"  · {s['employee_name']}: gross {s['gross']:.2f}, paye {s['paye']:.2f}, net {s['net']:.2f}")

    lines.append("\n--- LEAVE REQUESTS (recent) ---")
    for lv in leaves[:30]:
        lines.append(f"- id={lv['id']} | {lv['employee_name']} | {lv['leave_type']} | "
                     f"{lv['start_date']}→{lv['end_date']} ({lv['days']}d) | {lv['status']}")

    lines.append("\n--- ATTENDANCE (recent) ---")
    for a in attendance[:30]:
        emp = next((e for e in employees if e["id"] == a["employee_id"]), {})
        nm = f"{emp.get('first_name', '?')} {emp.get('last_name', '')}".strip()
        lines.append(f"- {a['date']} | {nm} | {a['hours']}h regular + {a['overtime_hours']}h OT")

    lines.append("\n--- AUDIT LOG (last 50) ---")
    for au in audits:
        meta = " · ".join(f"{k}={v}" for k, v in (au.get("meta") or {}).items())
        lines.append(f"- {au['ts'][:19]} | {au['user_email']} | {au['action']} | {au['resource']}"
                     + (f" | {meta}" if meta else ""))

    return "\n".join(lines)


def _extract_plan(text: str):
    """Extract a JSON action plan from a markdown ```json``` fenced block."""
    if not text:
        return None
    # Find all fenced blocks; prefer the last valid one
    blocks = re.findall(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text)
    for block in reversed(blocks):
        try:
            plan = json.loads(block)
            if isinstance(plan, dict) and isinstance(plan.get("steps"), list) and plan["steps"]:
                return plan
        except Exception:
            continue
    return None


@router.get("/context")
async def assistant_context_preview(_: dict = Depends(require_admin)):
    return {"context": await _build_company_context()}


@router.post("/chat")
@limiter.limit("20/minute")
async def assistant_chat(request: Request, body: AssistantMessageIn, user: dict = Depends(get_current_user)):
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

    if body.include_context and user.get("role") == "admin":
        ctx = await _build_company_context()
        sys_msg += (
            "\n\n--- BEGIN LIVE COMPANY DATA ---\n"
            f"{ctx}\n"
            "--- END LIVE COMPANY DATA ---\n"
            "When the admin asks about anomalies, top performers, leave usage, or payroll trends, "
            "ground your answer in the data above. Use specific names, departments, and SLE figures."
        )

    if body.action_mode and user.get("role") == "admin":
        sys_msg += (
            "\n\n--- ACTION MODE ENABLED ---\n"
            "When the admin asks you to perform an action (approve leave, run payroll, log attendance, "
            "create leave requests), DO NOT execute it. Instead, respond with a SHORT one-line summary, "
            "then output a JSON code block describing the proposed plan. The admin will review and confirm "
            "before execution. Maximum 50 steps per plan.\n\n"
            "JSON schema:\n"
            "```json\n"
            "{\n"
            '  "title": "Short human-readable title",\n'
            '  "rationale": "1-2 sentences explaining what you will do and why",\n'
            '  "steps": [\n'
            '    {"type": "leave_decision", "leave_id": "<id>", "decision": "approved" | "rejected"},\n'
            '    {"type": "payroll_run", "year": 2026, "month": 3},\n'
            '    {"type": "attendance_log", "employee_id": "<id>", "date": "YYYY-MM-DD", "hours": 8, "overtime_hours": 0}\n'
            "  ]\n"
            "}\n"
            "```\n"
            "Use real ids from the LIVE COMPANY DATA above. Only emit steps for actions that match the user's intent. "
            "If the user just asked a question (not an action), do NOT emit a JSON block."
        )

    chat = LlmChat(
        api_key=os.environ["EMERGENT_LLM_KEY"],
        session_id=sid,
        system_message=sys_msg,
    ).with_model("anthropic", "claude-sonnet-4-5-20250929")

    await db.assistant_messages.insert_one({
        "id": str(uuid.uuid4()), "session_id": sid, "role": "user",
        "content": body.message, "user_id": user["id"], "ts": iso(now_utc()),
    })

    reply = None
    try:
        reply = await chat.send_message(UserMessage(text=body.message))
    except Exception as e:
        logger.exception("LLM error")
        raise HTTPException(502, f"AI error: {e}")

    await db.assistant_messages.insert_one({
        "id": str(uuid.uuid4()), "session_id": sid, "role": "assistant",
        "content": reply, "user_id": user["id"], "ts": iso(now_utc()),
    })

    plan = _extract_plan(reply) if body.action_mode and user.get("role") == "admin" else None
    return {"session_id": sid, "reply": reply, "plan": plan}


@router.get("/history/{sid}")
async def assistant_history(sid: str, _: dict = Depends(get_current_user)):
    return await db.assistant_messages.find({"session_id": sid}, {"_id": 0}).sort("ts", 1).to_list(200)


# ---------- Action Plan Execution ----------
async def _exec_step(step, user: dict, plan_title: str) -> dict:
    """Execute a single validated PlanStep. Returns a result dict."""
    t = step.type
    meta_base = {"plan_title": plan_title}
    if t == "leave_decision":
        res = await db.leave_requests.update_one(
            {"id": step.leave_id}, {"$set": {"status": step.decision}}
        )
        if not res.matched_count:
            raise ValueError(f"leave {step.leave_id} not found")
        await audit(f"ai_leave_{step.decision}", f"leave_requests/{step.leave_id}", user, meta_base)
        return {"detail": f"Leave {step.leave_id} {step.decision}"}

    if t == "payroll_run":
        doc = await run_payroll(step.year, step.month, user, audit_action="ai_payroll_run")
        return {"detail": f"Payroll {doc['period']} run, net SLE {doc['totals']['net']:,.2f}"}

    if t == "attendance_log":
        doc = {
            "id": str(uuid.uuid4()),
            "employee_id": step.employee_id,
            "date": step.date,
            "hours": step.hours,
            "overtime_hours": step.overtime_hours,
            "notes": step.notes or "[AI-logged]",
            "created_at": iso(now_utc()),
        }
        await db.attendance.insert_one(doc)
        await audit("ai_attendance_log", f"attendance/{doc['id']}", user, {**meta_base, "date": step.date})
        return {"detail": f"Logged {step.hours}h on {step.date}"}

    if t == "leave_create":
        emp = await db.employees.find_one({"id": step.employee_id}, {"_id": 0})
        doc = {
            "id": str(uuid.uuid4()),
            "employee_id": step.employee_id,
            "employee_name": f'{emp["first_name"]} {emp["last_name"]}' if emp else "Unknown",
            "leave_type": step.leave_type,
            "start_date": step.start_date,
            "end_date": step.end_date,
            "days": step.days,
            "reason": step.reason or "[AI-created]",
            "status": "pending",
            "created_at": iso(now_utc()),
        }
        await db.leave_requests.insert_one(doc)
        await audit("ai_leave_create", f"leave_requests/{doc['id']}", user, meta_base)
        return {"detail": f"Leave request created for {doc['employee_name']}"}

    raise ValueError(f"Unknown step type: {t}")


@router.post("/action/execute")
async def execute_plan(body: ActionPlanIn, user: dict = Depends(require_admin)):
    """Execute a confirmed AI-generated action plan. Each step is audited individually."""
    plan: ActionPlan = body.plan
    results = []
    for i, step in enumerate(plan.steps):
        try:
            r = await _exec_step(step, user, plan.title)
            results.append({"step": i, "type": step.type, "status": "ok", **r})
        except Exception as e:
            logger.exception("plan step %s failed", i)
            results.append({"step": i, "type": step.type, "status": "error", "detail": str(e)})
    return {
        "executed": len([r for r in results if r["status"] == "ok"]),
        "results": results,
    }
