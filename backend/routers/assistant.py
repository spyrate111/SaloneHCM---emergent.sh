"""AI Assistant: chat (with optional context + action mode), context preview, history, action plan execute."""
import os
import re
import json
import uuid
import logging

from fastapi import APIRouter, HTTPException, Depends, Request

from core import db, get_current_user, require_admin, now_utc, iso, limiter, tenant_filter, require_feature
from models import AssistantMessageIn, ActionPlanIn, ActionPlan
from . import _ai_context, _ai_executor

logger = logging.getLogger("salonehcm.assistant")
router = APIRouter(prefix="/assistant", tags=["assistant"], dependencies=[Depends(require_feature("ai_assistant"))])


SYSTEM_BASE = (
    "You are SaloneHCM Assistant — an expert on Sierra Leone HR, labor law (Employment Act 2023), "
    "NRA PAYE tax bands, NASSIT contributions (employee 5%, employer 10% of basic), and payroll best practices. "
    "Answer in clear, concise tone. Use Sierra Leonean Leone (SLE) currency. When asked about payroll, "
    "explain the calculation steps. Keep replies under 200 words unless detail is requested."
)

ACTION_MODE_PROMPT = (
    "\n\n--- ACTION MODE ENABLED ---\n"
    "When the admin asks you to perform an action (approve leave, run payroll, log attendance, "
    "create leave requests, or simulate a salary scenario), DO NOT execute it. Instead, respond "
    "with a SHORT one-line summary, then output a JSON code block describing the proposed plan. "
    "The admin will review and confirm before execution. Maximum 50 steps per plan.\n\n"
    "JSON schema:\n"
    "```json\n"
    "{\n"
    '  "title": "Short human-readable title",\n'
    '  "rationale": "1-2 sentences explaining what you will do and why",\n'
    '  "steps": [\n'
    '    {"type": "leave_decision", "leave_id": "<id>", "decision": "approved" | "rejected"},\n'
    '    {"type": "payroll_run", "year": 2026, "month": 3},\n'
    '    {"type": "attendance_log", "employee_id": "<id>", "date": "YYYY-MM-DD", "hours": 8, "overtime_hours": 0},\n'
    '    {"type": "payroll_simulate", "title": "Eng +10%",\n'
    '      "rules": [{"name":"Eng raise","target":"department","department":"Engineering","basic_pct_change":10}]},\n'
    '    {"type": "scenario_apply", "scenario_id": "<saved-scenario-id>"}\n'
    "  ]\n"
    "}\n"
    "```\n"
    "Use real ids from the LIVE COMPANY DATA above. Only emit steps for actions that match the user's intent. "
    "If the user just asked a question (not an action), do NOT emit a JSON block."
)


def _extract_plan(text: str):
    """Extract a JSON action plan from a markdown fenced block."""
    if not text:
        return None
    blocks = re.findall(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text)
    for block in reversed(blocks):
        try:
            plan = json.loads(block)
            if isinstance(plan, dict) and isinstance(plan.get("steps"), list) and plan["steps"]:
                return plan
        except Exception:
            continue
    return None


async def _build_system_message(user: dict, include_context: bool, action_mode: bool) -> str:
    sys_msg = SYSTEM_BASE
    if include_context and user.get("role") == "admin":
        ctx = await _ai_context.build(user)
        sys_msg += (
            "\n\n--- BEGIN LIVE COMPANY DATA ---\n"
            f"{ctx}\n"
            "--- END LIVE COMPANY DATA ---\n"
            "When the admin asks about anomalies, top performers, leave usage, or payroll trends, "
            "ground your answer in the data above."
        )
    if action_mode and user.get("role") == "admin":
        sys_msg += ACTION_MODE_PROMPT
    return sys_msg


@router.get("/context")
async def assistant_context_preview(user: dict = Depends(require_admin)):
    return {"context": await _ai_context.build(user)}


@router.post("/chat")
@limiter.limit("20/minute")
async def assistant_chat(request: Request, body: AssistantMessageIn, user: dict = Depends(get_current_user)):
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
    except Exception as e:
        raise HTTPException(500, f"LLM lib unavailable: {e}")

    sid = body.session_id or str(uuid.uuid4())
    sys_msg = await _build_system_message(user, body.include_context, body.action_mode)

    chat = LlmChat(
        api_key=os.environ["EMERGENT_LLM_KEY"],
        session_id=sid,
        system_message=sys_msg,
    ).with_model("anthropic", "claude-sonnet-4-5-20250929")

    await db.assistant_messages.insert_one({
        "id": str(uuid.uuid4()),
        "company_id": user["company_id"],
        "session_id": sid,
        "role": "user",
        "content": body.message,
        "user_id": user["id"],
        "ts": iso(now_utc()),
    })

    reply: str = ""
    try:
        reply = await chat.send_message(UserMessage(text=body.message))
    except Exception as e:
        logger.exception("LLM error")
        raise HTTPException(502, f"AI error: {e}") from e

    await db.assistant_messages.insert_one({
        "id": str(uuid.uuid4()),
        "company_id": user["company_id"],
        "session_id": sid,
        "role": "assistant",
        "content": reply,
        "user_id": user["id"],
        "ts": iso(now_utc()),
    })

    plan = _extract_plan(reply) if body.action_mode and user.get("role") == "admin" else None
    return {"session_id": sid, "reply": reply, "plan": plan}


@router.get("/history/{sid}")
async def assistant_history(sid: str, user: dict = Depends(get_current_user)):
    return await db.assistant_messages.find(
        {"session_id": sid, **tenant_filter(user)},
        {"_id": 0},
    ).sort("ts", 1).to_list(200)


@router.post("/action/execute")
async def execute_plan(body: ActionPlanIn, user: dict = Depends(require_feature("ai_action_mode"))):
    """Execute a confirmed AI-generated action plan. Each step is audited individually."""
    if user.get("role") != "admin":
        raise HTTPException(403, "Admin only")
    plan: ActionPlan = body.plan
    results = []
    for i, step in enumerate(plan.steps):
        try:
            step_result = await _ai_executor.exec_step(step, user, plan.title)
            results.append({"step": i, "type": step.type, "status": "ok", **step_result})
        except Exception as e:
            logger.exception("plan step %s failed", i)
            results.append({"step": i, "type": step.type, "status": "error", "detail": str(e)})
    return {
        "executed": len([row for row in results if row["status"] == "ok"]),
        "results": results,
    }
