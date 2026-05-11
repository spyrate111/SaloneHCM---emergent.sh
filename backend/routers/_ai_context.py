"""AI Assistant — live company data context builder, scoped per tenant."""
from core import db, tenant_filter


async def _employees_section(tf: dict, lines: list) -> list[dict]:
    employees = await db.employees.find(tf, {"_id": 0}).to_list(2000)
    dept_counts: dict[str, int] = {}
    for e in employees:
        dept_counts[e["department"]] = dept_counts.get(e["department"], 0) + 1
    lines.append(f"Total employees: {len(employees)}")
    lines.append("Departments: " + ", ".join(f"{k}({v})" for k, v in dept_counts.items()))
    lines.append("\n--- EMPLOYEES (full) ---")
    for e in employees:
        lines.append(
            f"- id={e['id']} | {e['first_name']} {e['last_name']} | {e['job_title']} | {e['department']} | "
            f"basic SLE {e['basic_salary_sle']:.2f} + allow {e['allowances_sle']:.2f} | status {e['status']}"
        )
    return employees


async def _payroll_section(tf: dict, lines: list) -> None:
    runs = await db.payroll_runs.find(tf, {"_id": 0}).sort("created_at", -1).to_list(3)
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


async def _leave_section(tf: dict, lines: list) -> None:
    leaves = await db.leave_requests.find(tf, {"_id": 0}).sort("created_at", -1).to_list(30)
    lines.append("\n--- LEAVE REQUESTS (recent) ---")
    for lv in leaves:
        lines.append(
            f"- id={lv['id']} | {lv['employee_name']} | {lv['leave_type']} | "
            f"{lv['start_date']}→{lv['end_date']} ({lv['days']}d) | {lv['status']}"
        )


async def _attendance_section(tf: dict, employees: list[dict], lines: list) -> None:
    attendance = await db.attendance.find(tf, {"_id": 0}).sort("date", -1).to_list(30)
    lines.append("\n--- ATTENDANCE (recent) ---")
    for a in attendance:
        emp = next((e for e in employees if e["id"] == a["employee_id"]), {})
        nm = f"{emp.get('first_name', '?')} {emp.get('last_name', '')}".strip()
        lines.append(f"- {a['date']} | {nm} | {a['hours']}h regular + {a['overtime_hours']}h OT")


async def _audit_section(tf: dict, lines: list) -> None:
    audits = await db.audit_logs.find(tf, {"_id": 0}).sort("ts", -1).to_list(50)
    lines.append("\n--- AUDIT LOG (last 50) ---")
    for au in audits:
        meta = " · ".join(f"{k}={v}" for k, v in (au.get("meta") or {}).items())
        lines.append(
            f"- {au['ts'][:19]} | {au.get('user_email','?')} | {au['action']} | {au['resource']}"
            + (f" | {meta}" if meta else "")
        )


async def _scenarios_section(tf: dict, lines: list) -> None:
    scenarios = await db.payroll_scenarios.find(tf, {"_id": 0}).sort("created_at", -1).to_list(20)
    lines.append("\n--- SAVED PAYROLL SCENARIOS ---")
    for s in scenarios:
        approver = f" | approver={s['approver_email']}" if s.get("approver_email") else ""
        applied = " | applied" if s.get("applied") else ""
        lines.append(
            f"- id={s['id']} | '{s['title']}' | status={s.get('approval_status')}{applied}{approver}"
            f" | rules={len(s.get('rules', []))}"
        )


async def build(user: dict) -> str:
    """Compose the full live-data context for the AI, scoped to the user's company."""
    tf = tenant_filter(user)
    lines = ["=== SALONEHCM COMPANY DATA SNAPSHOT ==="]
    employees = await _employees_section(tf, lines)
    await _payroll_section(tf, lines)
    await _leave_section(tf, lines)
    await _attendance_section(tf, employees, lines)
    await _audit_section(tf, lines)
    await _scenarios_section(tf, lines)
    return "\n".join(lines)
