// Tour module definitions — each module has a mock product screen
// and a list of popup steps that walk the user through it.
//
// Steps reference a `selector` (data-tour-step id within the mock screen)
// and the popup is positioned anchored to that element.

export const TOUR_MODULES = [
  {
    id: "overview",
    title: "Overview",
    subtitle: "Your daily command center",
    steps: [
      { id: "ov-1", anchor: "kpi-payroll",   side: "right",  body: "Run a full month of payroll in under 2 hours — PAYE and NASSIT computed automatically against the latest SLE bands." },
      { id: "ov-2", anchor: "kpi-headcount", side: "right",  body: "Active headcount with month-over-month delta. Ghost-worker exceptions flagged in red on the same line." },
      { id: "ov-3", anchor: "kpi-compliance",side: "left",   body: "Live compliance score — NRA, NASSIT, GST and MoF approvals roll up to one number you can prove to an auditor." },
      { id: "ov-4", anchor: "quick-actions", side: "top",    body: "One-click for the things you do every month: run payroll, file PAYE, send payslips, post to GL." },
      { id: "ov-5", anchor: "ai-card",       side: "left",   body: "Ask the AI Assistant anything — in English or Krio. Admins can put it in Action Mode and let it file returns directly." },
    ],
  },
  {
    id: "run-payroll",
    title: "Run payroll",
    subtitle: "From timesheets to bank file in 3 clicks",
    steps: [
      { id: "rp-1", anchor: "period-picker", side: "right", body: "Pick a pay period. SaloneHCM auto-detects the cycle from your last close and pre-populates everything." },
      { id: "rp-2", anchor: "earnings-grid", side: "top",   body: "Earnings, deductions, allowances and sector presets all in one grid. Each cell tells you which tier rule drove the number." },
      { id: "rp-3", anchor: "totals-strip",  side: "top",   body: "Live totals — gross, PAYE, NASSIT employer + employee, net. Watch them recalc as you edit a row." },
      { id: "rp-4", anchor: "approve-btn",   side: "left",  body: "Two-step MoF approval baked in. Once approved, the bank file (Rokel / SLCB / UBA / Ecobank) generates with one more click." },
    ],
  },
  {
    id: "hire-person",
    title: "Hire someone",
    subtitle: "From candidate to first payslip in 5 minutes",
    steps: [
      { id: "hp-1", anchor: "candidate-card",side: "right", body: "Pull a candidate from the Talent ATS or add a brand-new hire. Either way, the form below pre-fills what it can." },
      { id: "hp-2", anchor: "compensation",  side: "top",   body: "Pick a grade and step — SaloneHCM proposes a salary band, computes PAYE and NASSIT impact in real time, and warns you about ghost-worker risks." },
      { id: "hp-3", anchor: "establishment", side: "left",  body: "Tie the new hire to an approved establishment position with its budget code attached. No off-budget surprises later." },
      { id: "hp-4", anchor: "send-offer",    side: "left",  body: "Generate the offer PDF in Krio or English, send by email or +232 SMS, and the candidate self-serves the rest." },
    ],
  },
];
