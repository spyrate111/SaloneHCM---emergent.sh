# SaloneHCM — Product Requirements

## Original Problem Statement
SaloneHCM — Sierra Leone Human Capital Management & Payroll System. Cloud-based enterprise-grade HCM and payroll platform tailored to Sierra Leone's labor laws, tax framework (NRA PAYE, NASSIT), and financial regulations. Feature parity with ADP Workforce Now, Gusto, Paychex Flex, Rippling — localized for Sierra Leonean businesses. Currency: Sierra Leonean Leone (SLE). Twelve modules across Lite/Professional/Enterprise/Gov tiers.

## Architecture
- React 19 + Tailwind + shadcn/ui frontend
- FastAPI backend (`/api` prefix)
- MongoDB (Motor) — collections: users, employees, payroll_runs, leave_requests, attendance, assistant_messages
- JWT (Bearer + httpOnly cookie) auth
- Anthropic Claude Sonnet 4.5 via Emergent Universal LLM key for AI Assistant

## User Personas
- HR Admin / Payroll Officer (admin role): runs payroll, manages employees, approves leave
- Employee (employee role): sees payslip, requests leave, logs attendance, AI assistant

## Implemented (Feb 2026 — v1.0)
- Auth: JWT login/logout/me, admin + employee roles, seeded admin + 10 demo employees
- Dashboard: KPIs (headcount, payroll cost, pending leaves, last run), payroll trend area chart, departments bar chart, quick actions
- Employees: list, search, create, detail page with computed payslip
- Payroll Engine: 3-step wizard (Period → Review → Confirm), gross-to-net using SL PAYE bands + NASSIT 5%/10%, run history
- Compliance & Tax: YTD PAYE/NASSIT, PAYE tax tables, per-period CSV export for NRA
- Leave: request + approve/reject, status badges, employee + admin views
- Time & Attendance: log hours/overtime, list view
- AI HR Assistant: Claude Sonnet 4.5 chat, persisted history, suggested prompts
- Self-Service: employee payslip + leave history
- Settings: read-only org/pay config

## Sierra Leone Payroll Rules Used
- NASSIT: 5% employee + 10% employer of basic
- PAYE bands (monthly SLE): 0–800 (0%), 800–2,200 (15%), 2,200–3,600 (20%), 3,600–5,000 (25%), 5,000–7,500 (30%), >7,500 (35%)

## Backlog (P0 → P2)
- P0: Multi-tenant company support, payslip PDF download, full-month attendance summary
- P1: Benefits administration, performance reviews, recruitment ATS, document vault uploads
- P2: Mobile ESS app, advanced analytics, GovTier (ministry payrolls), bank file export (NRC clearing)
