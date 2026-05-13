import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import api from "../lib/api";
import { Landmark, ShieldCheck, Users, Wallet, Receipt, ArrowDownToLine, FileCheck, Eye } from "lucide-react";

const fmtSLE = (v) => new Intl.NumberFormat("en", { style: "currency", currency: "SLE", maximumFractionDigits: 0 }).format(v);

export default function Transparency() {
  const { slug } = useParams();
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    api.get(`/public/transparency/${slug}`)
      .then((r) => setData(r.data))
      .catch((e) => setErr(e?.response?.data?.detail || "Portal not found"));
  }, [slug]);

  if (err) {
    return (
      <div className="min-h-screen grid place-items-center bg-[#F7F6F2] p-6">
        <div className="text-center max-w-md">
          <Landmark className="w-12 h-12 mx-auto text-[#A1A5AB]" strokeWidth={1.3} />
          <h1 className="font-heading text-2xl font-bold mt-4">Transparency portal not found</h1>
          <p className="text-sm text-[#525860] mt-2">{err}</p>
        </div>
      </div>
    );
  }
  if (!data) return null;
  const { organization, totals, ministries, last_payroll, compliance, as_of } = data;

  return (
    <div className="min-h-screen bg-[#F7F6F2]" data-testid="transparency-page">
      {/* Hero */}
      <header className="bg-gradient-to-br from-[#133326] via-[#0F281E] to-[#26547C] text-white relative overflow-hidden">
        <div className="absolute -top-20 -right-20 w-80 h-80 rounded-full bg-[#D1603D]/20 blur-3xl pointer-events-none" />
        <div className="max-w-6xl mx-auto px-6 sm:px-10 py-12 sm:py-16 relative">
          <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.22em] text-white/60">
            <ShieldCheck className="w-3.5 h-3.5" strokeWidth={1.7} /> Open Government · Transparency Portal
          </div>
          <h1 className="font-heading text-3xl sm:text-5xl font-bold mt-3 leading-tight" data-testid="org-name">
            {organization.name}
          </h1>
          <p className="text-white/75 mt-3 text-base sm:text-lg max-w-3xl leading-relaxed">
            Publicly-published payroll, compliance, and headcount figures. Anonymised — no personal information disclosed.
            Updated continuously from the SaloneHCM platform.
          </p>
          <div className="mt-5 flex items-center gap-3 text-xs text-white/70 font-data flex-wrap">
            <span>As of {new Date(as_of).toLocaleString()}</span>
            <span className="text-white/40">·</span>
            <span>{organization.country}</span>
            {organization.tier_label && (
              <>
                <span className="text-white/40">·</span>
                <span>Verified by {organization.tier_label}</span>
              </>
            )}
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-6 sm:px-10 py-8 sm:py-12 space-y-8">
        {/* National-level KPIs */}
        <section data-testid="kpis" className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <KPI icon={Users} label="Total civil servants" value={totals.headcount.toLocaleString()} sub={`Across ${totals.ministries} ministries`} accent="bg-[#26547C]" />
          <KPI icon={Wallet} label="Monthly gross payroll" value={fmtSLE(totals.monthly_gross_sle)} sub="Active employees" accent="bg-[#133326]" />
          <KPI icon={Receipt} label="Monthly PAYE remitted" value={fmtSLE(totals.monthly_paye_sle)} sub="To NRA" accent="bg-[#D1603D]" />
          <KPI icon={ArrowDownToLine} label="Monthly NASSIT" value={fmtSLE(totals.monthly_nassit_sle)} sub="Employee + Employer" accent="bg-[#2D7A5D]" />
        </section>

        {/* Per-ministry table */}
        <section className="bg-white border border-[#E2DFD6] rounded-xl overflow-hidden">
          <div className="px-6 py-4 border-b border-[#E2DFD6] flex items-center gap-2">
            <Landmark className="w-5 h-5 text-[#26547C]" strokeWidth={1.6} />
            <div>
              <h2 className="font-heading text-lg font-semibold">By ministry</h2>
              <p className="text-xs text-[#686D76] mt-0.5">Ranked by monthly gross payroll. Headcount only — no individual data is disclosed.</p>
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm" data-testid="ministry-table">
              <thead className="bg-[#F7F6F2]">
                <tr>{["#", "Ministry", "Headcount", "Gross / month", "PAYE / month", "NASSIT / month"].map((h) => (
                  <th key={h} className="text-left text-[10px] uppercase tracking-wider text-[#525860] py-3 px-4 font-medium">{h}</th>
                ))}</tr>
              </thead>
              <tbody>
                {ministries.map((m, i) => (
                  <tr key={m.name} className="border-t border-[#E2DFD6]">
                    <td className="py-3 px-4 font-data text-[#686D76]">{i + 1}</td>
                    <td className="py-3 px-4 font-medium">{m.name}</td>
                    <td className="py-3 px-4 font-data">{m.headcount}</td>
                    <td className="py-3 px-4 font-data font-semibold">{fmtSLE(m.monthly_gross_sle)}</td>
                    <td className="py-3 px-4 font-data text-[#B84F2F]">{fmtSLE(m.monthly_paye_sle)}</td>
                    <td className="py-3 px-4 font-data text-[#26547C]">{fmtSLE(m.monthly_nassit_sle)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        {/* Compliance trail */}
        <section className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="bg-white border border-[#E2DFD6] rounded-lg p-6" data-testid="last-payroll">
            <div className="text-[10px] uppercase tracking-wider text-[#525860] flex items-center gap-2">
              <Wallet className="w-3.5 h-3.5" /> Most recent payroll
            </div>
            {last_payroll ? (
              <>
                <div className="font-heading text-2xl font-bold mt-2 font-data">{last_payroll.period}</div>
                <div className="text-xs text-[#686D76] mt-1">Run on {new Date(last_payroll.ran_at).toLocaleDateString()}</div>
              </>
            ) : (
              <div className="text-sm text-[#686D76] mt-2">No payroll runs yet.</div>
            )}
          </div>
          <div className="bg-white border border-[#E2DFD6] rounded-lg p-6" data-testid="compliance">
            <div className="text-[10px] uppercase tracking-wider text-[#525860] flex items-center gap-2">
              <FileCheck className="w-3.5 h-3.5" /> NRA filings (last 12 months)
            </div>
            <div className="font-heading text-2xl font-bold mt-2 font-data text-[#2D7A5D]">
              {compliance.returns_filed_12m}
              <span className="text-base text-[#A1A5AB] font-normal"> returns filed</span>
            </div>
            <div className="text-xs text-[#686D76] mt-1">
              {compliance.most_recent_filing ? `Most recent: ${compliance.most_recent_filing}` : "No filings recorded."}
            </div>
          </div>
        </section>

        {/* Footer */}
        <footer className="border-t border-[#E2DFD6] pt-6 text-xs text-[#686D76] text-center space-y-2">
          <div className="flex items-center justify-center gap-1.5">
            <ShieldCheck className="w-3.5 h-3.5 text-[#2D7A5D]" /> Verified compliance with NRA PAYE bands and NASSIT employer/employee schedules
          </div>
          <div>Powered by <span className="font-medium text-[#133326]">SaloneHCM</span> · Open Government Partnership initiative</div>
        </footer>
      </main>
    </div>
  );
}

function KPI({ icon: Icon, label, value, sub, accent }) {
  return (
    <div className="bg-white border border-[#E2DFD6] rounded-lg p-4 flex items-start justify-between gap-3">
      <div className="min-w-0">
        <div className="text-[10px] uppercase tracking-[0.16em] text-[#525860]">{label}</div>
        <div className="font-heading text-xl sm:text-2xl font-bold mt-1 font-data">{value}</div>
        {sub && <div className="text-[10px] text-[#686D76] mt-0.5 truncate">{sub}</div>}
      </div>
      <div className={`w-9 h-9 rounded-md ${accent} grid place-items-center shrink-0`}>
        <Icon className="w-[18px] h-[18px] text-white" strokeWidth={1.5} />
      </div>
    </div>
  );
}
