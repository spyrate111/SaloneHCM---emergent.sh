# SaloneHCM — Product Requirements

## Original Problem Statement
SaloneHCM — Sierra Leone Human Capital Management & Payroll System. Cloud-based enterprise-grade HCM and payroll platform tailored to Sierra Leone's labor laws, tax framework (NRA PAYE, NASSIT), and financial regulations. Feature parity with ADP Workforce Now, Gusto, Paychex Flex, Rippling — localized for Sierra Leonean businesses. Currency: Sierra Leonean Leone (SLE). Twelve modules across Lite/Professional/Enterprise/Gov tiers.

## Mission (as displayed in app)
Build a cloud-based, enterprise-grade Human Capital Management (HCM) and payroll platform tailored specifically to Sierra Leone's labor laws, tax framework, and financial regulations — offering the same depth and feature parity as ADP Workforce Now, Gusto, Sure Payroll, Paychex Flex, and Rippling — but localized for Sierra Leonean businesses of all sizes, from SMEs to large enterprises all around the country and the Government of Sierra Leone.

## Architecture
- React 19 + Tailwind + shadcn/ui frontend, JWT in `sessionStorage`
- FastAPI backend modularised under `/app/backend/routers/*` (all routes under `/api`)
- MongoDB (Motor) — collections: users, employees, payroll_runs, leave_requests, attendance, assistant_messages, payroll_scenarios, **documents**, audit_logs
- Emergent Object Storage for file uploads (uses `EMERGENT_LLM_KEY`)
- Anthropic Claude Sonnet 4.5 via Emergent Universal LLM key for AI Assistant
- ReportLab for PDF (payslip + Decision Brief)
- slowapi rate-limiting with X-Forwarded-For aware `_client_ip`

## User Personas
- HR Admin / Payroll Officer (admin role): runs payroll, manages employees, approves leave, uploads documents
- Employee (employee role): sees payslip, requests leave, logs attendance, views own documents, AI assistant
- Manager (employee with direct reports): views team page, approves direct-report leave

## Implemented
### v1.0 (Feb 2026)
- Auth: JWT login/logout/me, admin + employee roles, seeded admin + 10 demo employees
- Dashboard: KPIs, payroll trend, departments bar, quick actions
- Employees: CRUD + detail with computed payslip
- Payroll Engine: 3-step wizard, gross-to-net (SL PAYE bands + NASSIT 5%/10%), run history
- Compliance & Tax: YTD PAYE/NASSIT, per-period CSV export
- Leave + Attendance, AI HR Assistant (Claude Sonnet 4.5), Settings, Self-Service

### v1.1
- Benefits, Talent, Analytics modules
- AI Assistant Action Mode (executes HR endpoints), What-if Payroll Simulator
- Scenario Save / Approve / Compare workflow
- Backend refactor: monolithic `server.py` → modular `routers/`
- Rate limiting (slowapi) with X-Forwarded-For

### v1.2 (May 2026)
- Manager Self-Service `/team` (own reports) + `/team/:eid` (admin pick)
- Manager Leave Approval — direct manager can approve/reject reports' leave
- Decision Brief PDF — `/api/payroll/scenarios/compare/pdf` via ReportLab
- **Document Vault** — Emergent Object Storage backed; categories: contract, certificate, p9_form, payslip, id_document, other; PDF/DOCX/JPG/PNG; max 10MB; soft-delete; admin upload/delete, employee read-own
- **Mission statement** displayed on Settings page

## Sierra Leone Payroll Rules Used
- NASSIT: 5% employee + 10% employer of basic
- PAYE bands (monthly SLE): 0–800 (0%), 800–2,200 (15%), 2,200–3,600 (20%), 3,600–5,000 (25%), 5,000–7,500 (30%), >7,500 (35%)

## Key API Endpoints
- `POST /api/auth/login` → `{ token, role, employee_id }`
- `GET /api/employees`, `GET /api/team/me`, `GET /api/team/managers`
- `POST /api/payroll/runs`, `GET /api/payroll/runs/{id}/payslip/{eid}.pdf`
- `POST /api/payroll/simulate`, `/scenarios/*`, `/scenarios/compare`, `/scenarios/compare/pdf`
- `PUT /api/leave/{lid}/decision` — admin OR direct manager
- `POST /api/documents/upload` (multipart), `GET /api/documents`, `/documents/{id}/download`, `DELETE /api/documents/{id}`
- `POST /api/assistant/chat`

## Backlog (P0 → P2)
### P1
- Multi-tenant + GovTier (Batch C) — `company_id` on every collection, tier gating (Lite/Pro/Enterprise/Gov)
- Performance reviews, recruitment ATS expansions

### P2
- Twilio bulk SMS payslips (requires user API keys)
- Resend email approver notifications for scenarios (requires user API key)
- Mobile ESS PWA
- Bank file export (NRC clearing)
- Backend pytest regression suite at `/app/backend/tests`
- Cosmetic: Recharts width(-1) console warning (charts render fine)

## Test Credentials
See `/app/memory/test_credentials.md`.

## Architecture Notes for Future Agents
- All third-party integrations route through `integration_playbook_expert_v2`
- Emergent LLM key powers both AI Assistant **and** Object Storage init
- Token is in `sessionStorage` (key `salonehcm_token`); axios interceptor adds Bearer header
- Documents are soft-deleted (set `is_deleted=true`), storage has no native delete
- Storage init is lazy + cached at module level; auto-retry on 403 with fresh key
