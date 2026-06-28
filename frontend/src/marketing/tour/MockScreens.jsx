import { Wallet, Users, ShieldCheck, Calculator, FileSignature, Mail, Database, Sparkles, ChevronRight, ArrowUpRight, Building2 } from "lucide-react";

/* Three mock product screens used by the /tour wizard.
   These deliberately look like SaloneHCM product UI but are static —
   the goal is to give prospects a visual feel without spinning up a real tenant. */

export function OverviewMock() {
  return (
    <div className="bg-[#FAF8F2] p-6 lg:p-8 h-full overflow-auto" data-testid="mock-overview">
      <div className="flex items-baseline justify-between">
        <div>
          <div className="text-[10px] font-bold uppercase tracking-[0.16em] text-[#525860]">Dashboard</div>
          <h1 className="text-[24px] font-extrabold text-[#0F2C24]">Good morning, Aminata</h1>
          <p className="text-[12.5px] text-[#525860] mt-0.5">June 2026 cycle &middot; 142 active employees</p>
        </div>
        <span className="hidden sm:inline-flex items-center px-3 h-7 text-[10px] font-bold uppercase tracking-[0.14em] bg-[#0F2C24] text-white rounded-full">Government tier</span>
      </div>

      <div className="grid sm:grid-cols-3 gap-4 mt-6">
        <KpiTile testid="kpi-payroll"    icon={Wallet}      title="Payroll due"      value="SLE 184,720" sub="+2.3% vs May" tone="text-[#1f6f55]" />
        <KpiTile testid="kpi-headcount"  icon={Users}       title="Active headcount" value="142"          sub="3 new this month" tone="text-[#0F2C24]" />
        <KpiTile testid="kpi-compliance" icon={ShieldCheck} title="Compliance score" value="98 / 100"     sub="NRA + NASSIT current" tone="text-[#E07B4A]" />
      </div>

      <div className="grid lg:grid-cols-3 gap-4 mt-4">
        <div className="lg:col-span-2 bg-white border border-[#EAE7DF] rounded-xl p-5" data-tour-anchor="quick-actions">
          <div className="text-[10px] font-bold uppercase tracking-[0.14em] text-[#525860] mb-3">Quick actions</div>
          <div className="grid sm:grid-cols-2 gap-2.5">
            {[
              { icon: Calculator,   label: "Run June payroll",      hint: "3 clicks" },
              { icon: FileSignature,label: "File PAYE return",      hint: "Due Jul 15" },
              { icon: Mail,         label: "Send payslips by SMS",  hint: "Via Twilio +232" },
              { icon: Database,     label: "Post to General Ledger",hint: "Auto-mapped" },
            ].map((a) => {
              const Icon = a.icon;
              return (
                <button key={a.label} type="button" className="flex items-center justify-between bg-[#FAF8F2] hover:bg-[#F1EEE6] rounded-lg px-3.5 py-2.5 text-left transition-colors group">
                  <div className="flex items-center gap-2.5">
                    <Icon className="w-4 h-4 text-[#0F2C24]" />
                    <div>
                      <div className="text-[13px] font-extrabold text-[#0F2C24]">{a.label}</div>
                      <div className="text-[10px] text-[#525860]">{a.hint}</div>
                    </div>
                  </div>
                  <ChevronRight className="w-4 h-4 text-[#9aa0a6] group-hover:text-[#C02719]" />
                </button>
              );
            })}
          </div>
        </div>
        <div className="bg-gradient-to-br from-[#0F2C24] to-[#1f6f55] rounded-xl p-5 text-white" data-tour-anchor="ai-card">
          <div className="flex items-center gap-2">
            <div className="w-9 h-9 rounded-full bg-white/15 grid place-items-center"><Sparkles className="w-4 h-4 text-[#E07B4A]" /></div>
            <div>
              <div className="text-[12px] font-bold">AI Assistant</div>
              <div className="text-[10px] text-white/70">Action mode &middot; on</div>
            </div>
          </div>
          <p className="mt-3 text-[12.5px] text-white/85 leading-relaxed">
            &ldquo;Show me total PAYE owed for Q2 and prep the return for filing.&rdquo;
          </p>
          <div className="mt-3 inline-flex items-center gap-1 text-[11px] font-bold text-[#E07B4A]">Computing&hellip; <ArrowUpRight className="w-3 h-3" /></div>
        </div>
      </div>

      <div className="bg-white border border-[#EAE7DF] rounded-xl p-5 mt-4">
        <div className="flex items-center justify-between mb-3">
          <div className="text-[10px] font-bold uppercase tracking-[0.14em] text-[#525860]">Compliance feed</div>
          <span className="text-[10px] text-[#1f6f55] font-bold">All current</span>
        </div>
        <ul className="space-y-2 text-[13px]">
          {[
            "NRA PAYE June return &mdash; ready to file",
            "NASSIT remittance &mdash; submitted Jun 12",
            "MoF approval &mdash; signed by Permanent Secretary",
            "Ghost-worker audit &mdash; 0 exceptions",
          ].map((t) => (
            <li key={t} className="flex items-center gap-2 text-[#0F2C24]">
              <ShieldCheck className="w-3.5 h-3.5 text-[#1f6f55]" />
              <span dangerouslySetInnerHTML={{ __html: t }} />
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

export function RunPayrollMock() {
  return (
    <div className="bg-[#FAF8F2] p-6 lg:p-8 h-full overflow-auto" data-testid="mock-payroll">
      <div className="flex items-baseline justify-between">
        <div>
          <div className="text-[10px] font-bold uppercase tracking-[0.16em] text-[#525860]">Payroll</div>
          <h1 className="text-[24px] font-extrabold text-[#0F2C24]">Run payroll &middot; June 2026</h1>
        </div>
        <button type="button" className="px-4 h-9 text-[12px] font-bold bg-[#C02719] text-white rounded-full" data-tour-anchor="approve-btn">
          Send for MoF approval
        </button>
      </div>

      <div className="mt-6 bg-white border border-[#EAE7DF] rounded-xl p-5" data-tour-anchor="period-picker">
        <div className="grid sm:grid-cols-3 gap-3">
          <Stat label="Pay period" value="01 Jun &mdash; 30 Jun 2026" />
          <Stat label="Pay date" value="Fri 28 Jun 2026" />
          <Stat label="Frequency" value="Monthly" />
        </div>
      </div>

      <div className="mt-4 bg-white border border-[#EAE7DF] rounded-xl overflow-hidden" data-tour-anchor="earnings-grid">
        <table className="w-full text-[12.5px]">
          <thead className="bg-[#F1EEE6]">
            <tr>
              {["Employee", "Grade", "Gross", "PAYE", "NASSIT", "Net"].map((h) => (
                <th key={h} className="text-left text-[10px] uppercase tracking-[0.1em] text-[#525860] py-2.5 px-4 font-bold">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {[
              ["Aminata Kamara",   "G14-S3", "SLE 18,200", "SLE 3,184",  "SLE 910",  "SLE 14,106"],
              ["Mohamed Sesay",    "G16-S1", "SLE 24,500", "SLE 4,902",  "SLE 1,225","SLE 18,373"],
              ["Foday Massaquoi",  "G10-S5", "SLE 11,800", "SLE 1,652",  "SLE 590",  "SLE  9,558"],
              ["Sia Kallon",       "G09-S2", "SLE  9,400", "SLE 1,128",  "SLE 470",  "SLE  7,802"],
              ["Kabba Lansana",    "G08-S4", "SLE  7,300", "SLE   730",  "SLE 365",  "SLE  6,205"],
            ].map(([n, g, gr, p, na, net], i) => (
              <tr key={n} className={i % 2 ? "bg-[#FAF8F2]/40" : ""}>
                <td className="py-2.5 px-4 font-semibold text-[#0F2C24]">{n}</td>
                <td className="py-2.5 px-4 text-[#525860] font-mono">{g}</td>
                <td className="py-2.5 px-4 font-mono text-[#0F2C24]">{gr}</td>
                <td className="py-2.5 px-4 font-mono text-[#C02719]">{p}</td>
                <td className="py-2.5 px-4 font-mono text-[#C02719]">{na}</td>
                <td className="py-2.5 px-4 font-mono font-bold text-[#1f6f55]">{net}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="mt-4 grid sm:grid-cols-4 gap-3" data-tour-anchor="totals-strip">
        <Tile label="Gross"  val="SLE 71,200" tone="text-[#0F2C24]" />
        <Tile label="PAYE"   val="SLE 11,596" tone="text-[#C02719]" />
        <Tile label="NASSIT" val="SLE  3,560" tone="text-[#C02719]" />
        <Tile label="Net"    val="SLE 56,044" tone="text-[#1f6f55]" hi />
      </div>
    </div>
  );
}

export function HirePersonMock() {
  return (
    <div className="bg-[#FAF8F2] p-6 lg:p-8 h-full overflow-auto" data-testid="mock-hire">
      <div className="flex items-baseline justify-between">
        <div>
          <div className="text-[10px] font-bold uppercase tracking-[0.16em] text-[#525860]">Hiring &middot; Step 2 of 4</div>
          <h1 className="text-[24px] font-extrabold text-[#0F2C24]">Hire a new employee</h1>
        </div>
        <button type="button" className="px-4 h-9 text-[12px] font-bold bg-[#C02719] text-white rounded-full" data-tour-anchor="send-offer">
          Generate &amp; send offer
        </button>
      </div>

      <div className="grid lg:grid-cols-3 gap-4 mt-6">
        <div className="lg:col-span-2 space-y-4">
          <div className="bg-white border border-[#EAE7DF] rounded-xl p-5" data-tour-anchor="candidate-card">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 rounded-full bg-[#FAF8F2] grid place-items-center text-[#0F2C24] font-extrabold">AB</div>
              <div className="flex-1">
                <div className="text-[15px] font-extrabold text-[#0F2C24]">Aisha Bangura</div>
                <div className="text-[11.5px] text-[#525860]">Pulled from ATS &middot; Senior Accountant pipeline</div>
              </div>
              <span className="text-[10px] font-bold uppercase tracking-[0.12em] bg-[#E6F2EC] text-[#1f6f55] px-2 py-1 rounded">Verified</span>
            </div>
            <div className="grid sm:grid-cols-2 gap-3 mt-4">
              <FieldRow label="Date of birth" value="14 Mar 1990" />
              <FieldRow label="NASSIT #" value="NS-A-0091-2014" />
              <FieldRow label="TIN" value="TIN-7783-Q" />
              <FieldRow label="Bank" value="Rokel &middot; 100-2294-001" />
            </div>
          </div>

          <div className="bg-white border border-[#EAE7DF] rounded-xl p-5" data-tour-anchor="compensation">
            <div className="text-[10px] font-bold uppercase tracking-[0.14em] text-[#525860] mb-3">Compensation</div>
            <div className="grid grid-cols-3 gap-3">
              <div className="bg-[#FAF8F2] rounded-lg p-3">
                <div className="text-[10px] uppercase tracking-wider text-[#525860]">Grade</div>
                <div className="text-[18px] font-extrabold text-[#0F2C24] font-mono mt-0.5">G13</div>
              </div>
              <div className="bg-[#FAF8F2] rounded-lg p-3">
                <div className="text-[10px] uppercase tracking-wider text-[#525860]">Step</div>
                <div className="text-[18px] font-extrabold text-[#0F2C24] font-mono mt-0.5">S2</div>
              </div>
              <div className="bg-[#FFE9E5] rounded-lg p-3">
                <div className="text-[10px] uppercase tracking-wider text-[#525860]">Proposed salary</div>
                <div className="text-[18px] font-extrabold text-[#C02719] font-mono mt-0.5">SLE 14,200</div>
              </div>
            </div>
            <div className="mt-3 text-[11px] text-[#525860]">PAYE impact: <strong className="text-[#0F2C24] font-mono">SLE 1,988/mo</strong> &middot; NASSIT employer: <strong className="text-[#0F2C24] font-mono">SLE 710/mo</strong></div>
          </div>
        </div>

        <div className="bg-white border border-[#EAE7DF] rounded-xl p-5" data-tour-anchor="establishment">
          <div className="text-[10px] font-bold uppercase tracking-[0.14em] text-[#525860] mb-3">Establishment slot</div>
          <div className="flex items-start gap-2">
            <Building2 className="w-5 h-5 text-[#1f6f55] mt-0.5" />
            <div>
              <div className="text-[13px] font-extrabold text-[#0F2C24] leading-snug">Senior Accountant</div>
              <div className="text-[11px] text-[#525860] mt-0.5">Ministry of Finance &middot; Directorate of Audit &middot; Accounts Unit</div>
            </div>
          </div>
          <div className="mt-4 space-y-2 text-[11.5px]">
            <Row k="Budget code" v="MoF-AUD-ACC-G13" />
            <Row k="Headcount limit" v="6" />
            <Row k="Currently filled" v="4 of 6" />
            <Row k="Vacant" v="2" tone="text-[#1f6f55] font-bold" />
          </div>
          <div className="mt-4 text-[11px] bg-[#E6F2EC] text-[#1f6f55] rounded px-2 py-1.5">
            On-budget &middot; no MoF override required.
          </div>
        </div>
      </div>
    </div>
  );
}

function KpiTile({ icon: Icon, title, value, sub, tone, testid }) {
  return (
    <div className="bg-white border border-[#EAE7DF] rounded-xl p-5" data-tour-anchor={testid}>
      <div className="flex items-center justify-between">
        <Icon className={`w-5 h-5 ${tone}`} />
        <span className="text-[10px] uppercase tracking-[0.12em] text-[#525860]">{title}</span>
      </div>
      <div className="mt-3 text-[26px] font-extrabold text-[#0F2C24] font-mono leading-none">{value}</div>
      <div className={`text-[11px] ${tone} font-semibold mt-1`}>{sub}</div>
    </div>
  );
}

function Stat({ label, value }) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-[0.12em] text-[#525860]">{label}</div>
      <div className="text-[15px] font-extrabold text-[#0F2C24] mt-0.5" dangerouslySetInnerHTML={{ __html: value }} />
    </div>
  );
}

function Tile({ label, val, tone, hi }) {
  return (
    <div className={`${hi ? "bg-[#0F2C24] text-white" : "bg-white border border-[#EAE7DF]"} rounded-xl p-4`}>
      <div className={`text-[10px] uppercase tracking-[0.12em] ${hi ? "text-white/70" : "text-[#525860]"}`}>{label}</div>
      <div className={`text-[20px] font-extrabold font-mono mt-1 ${hi ? "text-white" : tone}`}>{val}</div>
    </div>
  );
}

function FieldRow({ label, value }) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-[0.1em] text-[#525860]">{label}</div>
      <div className="text-[12.5px] font-semibold text-[#0F2C24] mt-0.5">{value}</div>
    </div>
  );
}

function Row({ k, v, tone = "text-[#0F2C24]" }) {
  return (
    <div className="flex items-center justify-between text-[11.5px]">
      <span className="text-[#525860]">{k}</span>
      <span className={`font-mono ${tone}`} dangerouslySetInnerHTML={{ __html: v }} />
    </div>
  );
}
