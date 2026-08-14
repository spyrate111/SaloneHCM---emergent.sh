import { useEffect, useState, useCallback } from "react";
import { useParams, Link } from "react-router-dom";
import api, { fmtSLE } from "../lib/api";
import { useFeatures } from "../lib/features";
import { toast } from "sonner";
import { ChevronLeft, Mail, Phone, MapPin, Briefcase, Calendar, Hash, Award, Tag, Save, QrCode, Printer, X } from "lucide-react";

export default function EmployeeDetail() {
  const { id } = useParams();
  const { has } = useFeatures();
  const [e, setE] = useState(null);
  const [slip, setSlip] = useState(null);
  // Civil-service refs
  const [grades, setGrades] = useState([]);
  const [budgets, setBudgets] = useState([]);
  const [cs, setCs] = useState({});
  const [savingCs, setSavingCs] = useState(false);
  const [qr, setQr] = useState(null);
  const [qrBusy, setQrBusy] = useState(false);

  const issueQr = async () => {
    setQrBusy(true);
    try {
      const r = await api.post(`/employees/${id}/onboarding-qr`, { ttl_days: 14 });
      setQr(r.data);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Could not issue QR");
    } finally {
      setQrBusy(false);
    }
  };

  const load = useCallback(() => api.get(`/employees/${id}`).then((r) => {
    setE(r.data);
    setCs({
      grade_code: r.data.grade_code || "",
      step_number: r.data.step_number || "",
      budget_code: r.data.budget_code || "",
      mda_ministry: r.data.mda_ministry || "",
      housing_allowance_enabled: r.data.housing_allowance_enabled ?? true,
      transport_allowance_enabled: r.data.transport_allowance_enabled ?? true,
      responsibility_allowance_enabled: r.data.responsibility_allowance_enabled ?? false,
      hardship_allowance_enabled: r.data.hardship_allowance_enabled ?? false,
    });
  }), [id]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    if (!has || !has("civil_service")) return;
    api.get("/civil-service/grades").then((r) => setGrades(r.data)).catch(() => {});
    api.get("/civil-service/budget-codes").then((r) => setBudgets(r.data)).catch(() => {});
  }, [has]);

  useEffect(() => {
    if (!e) return;
    api.post("/payroll/preview").then((r) => {
      const s = r.data.slips.find((x) => x.employee_id === e.id);
      if (s) setSlip(s);
    }).catch(() => {});
  }, [e]);

  const saveCs = async () => {
    setSavingCs(true);
    try {
      const payload = {};
      if (cs.grade_code) payload.grade_code = cs.grade_code;
      if (cs.step_number) payload.step_number = Number(cs.step_number);
      if (cs.budget_code) payload.budget_code = cs.budget_code;
      if (cs.mda_ministry) payload.mda_ministry = cs.mda_ministry;
      payload.housing_allowance_enabled = !!cs.housing_allowance_enabled;
      payload.transport_allowance_enabled = !!cs.transport_allowance_enabled;
      payload.responsibility_allowance_enabled = !!cs.responsibility_allowance_enabled;
      payload.hardship_allowance_enabled = !!cs.hardship_allowance_enabled;
      const res = await api.patch(`/civil-service/employees/${id}/profile`, payload);
      toast.success("Civil-service profile updated");
      // Refresh from server (basic salary may have been auto-synced from step)
      load();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Save failed");
    } finally {
      setSavingCs(false);
    }
  };

  const selectedGrade = grades.find((g) => g.code === cs.grade_code);

  if (!e) return <div className="text-sm text-[#525860]">Loading…</div>;

  return (
    <div className="space-y-6" data-testid="employee-detail">
      <Link to="/employees" className="inline-flex items-center gap-1.5 text-sm text-[#525860] hover:text-[#1A1C1E]">
        <ChevronLeft className="w-4 h-4" /> Back to employees
      </Link>

      <div className="bg-white border border-[#E2DFD6] rounded-lg p-6 flex items-center gap-5">
        <div className="w-20 h-20 rounded-full bg-[#0A4A1E] text-white grid place-items-center font-heading text-2xl font-bold">
          {e.first_name?.[0]}{e.last_name?.[0]}
        </div>
        <div className="flex-1">
          <div className="text-[10px] uppercase tracking-[0.16em] text-[#525860]">{e.department}</div>
          <h1 className="font-heading text-3xl font-bold mt-1">{e.first_name} {e.last_name}</h1>
          <div className="text-[#525860] text-sm mt-1">{e.job_title} · {e.employment_type}</div>
        </div>
        <span className="text-[11px] font-medium px-3 py-1 rounded-full bg-[#E4F7E7] text-[#17A035] uppercase tracking-wider">
          {e.status}
        </span>
        <button
          onClick={issueQr}
          disabled={qrBusy}
          className="ml-2 inline-flex items-center gap-1.5 text-xs bg-[#0A4A1E] hover:bg-[#063514] text-white px-3 py-2 rounded-md disabled:opacity-50"
          data-testid="employee-onboarding-qr-btn"
          title="Print a one-time QR that signs this employee in on their phone"
        >
          <QrCode className="w-3.5 h-3.5" /> {qrBusy ? "Issuing…" : "Onboarding QR"}
        </button>
      </div>

      {qr && <OnboardingQrModal qr={qr} onClose={() => setQr(null)} />}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <div className="lg:col-span-2 space-y-5">
          <div className="bg-white border border-[#E2DFD6] rounded-lg p-6 space-y-4">
            <h3 className="font-heading text-lg font-semibold">Profile</h3>
            {[
              [Mail, "Email", e.email],
              [Phone, "Phone", e.phone],
              [MapPin, "Location", e.location],
              [Briefcase, "Job title", e.job_title],
              [Calendar, "Hire date", e.hire_date],
              [Hash, "NASSIT No.", e.nassit_no],
              [Hash, "TIN", e.tin],
            ].map(([Icon, label, val]) => (
              <div key={label} className="flex items-center gap-4 py-2 border-b border-[#F1EEE6] last:border-0">
                <Icon className="w-4 h-4 text-[#A1A5AB]" strokeWidth={1.5} />
                <div className="text-xs uppercase tracking-wider text-[#525860] w-32">{label}</div>
                <div className="text-sm text-[#1A1C1E] font-data">{val || "—"}</div>
              </div>
            ))}
          </div>

          {has("civil_service") && (
            <div className="bg-white border border-[#E2DFD6] rounded-lg p-6 space-y-4" data-testid="cs-profile-editor">
              <div className="flex items-center justify-between flex-wrap gap-2">
                <h3 className="font-heading text-lg font-semibold inline-flex items-center gap-2">
                  <Award className="w-5 h-5 text-[#26547C]" strokeWidth={1.5} /> Civil-service profile
                </h3>
                <button data-testid="cs-save" onClick={saveCs} disabled={savingCs} className="inline-flex items-center gap-2 bg-[#0A4A1E] hover:bg-[#063514] text-white text-xs px-3 py-2 rounded-md disabled:opacity-50">
                  <Save className="w-3.5 h-3.5" /> {savingCs ? "Saving…" : "Save"}
                </button>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-[#525860] mb-1 uppercase tracking-wider">Grade</label>
                  <select data-testid="cs-grade" value={cs.grade_code} onChange={(ev) => setCs({ ...cs, grade_code: ev.target.value, step_number: "" })} className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm font-data">
                    <option value="">— Unassigned —</option>
                    {grades.map((g) => <option key={g.code} value={g.code}>{g.code} · {g.name}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-[#525860] mb-1 uppercase tracking-wider">Step</label>
                  <select data-testid="cs-step" value={cs.step_number} onChange={(ev) => setCs({ ...cs, step_number: ev.target.value })} disabled={!selectedGrade} className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm font-data disabled:bg-[#F7F6F2]">
                    <option value="">— Pick step —</option>
                    {(selectedGrade?.steps || []).map((s) => (
                      <option key={s.step_number} value={s.step_number}>Step {s.step_number} — {fmtSLE(s.monthly_amount_sle)}</option>
                    ))}
                  </select>
                </div>
                <div className="col-span-2">
                  <label className="block text-xs font-medium text-[#525860] mb-1 uppercase tracking-wider">Budget code</label>
                  <select data-testid="cs-budget" value={cs.budget_code} onChange={(ev) => {
                    const b = budgets.find((x) => x.code === ev.target.value);
                    setCs({ ...cs, budget_code: ev.target.value, mda_ministry: b?.ministry || cs.mda_ministry });
                  }} className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm font-data">
                    <option value="">— Unassigned —</option>
                    {budgets.map((b) => <option key={b.code} value={b.code}>{b.code} · {b.name}</option>)}
                  </select>
                </div>
                <div className="col-span-2">
                  <label className="block text-xs font-medium text-[#525860] mb-2 uppercase tracking-wider">Allowance toggles</label>
                  <div className="grid grid-cols-2 gap-2">
                    {[
                      ["housing_allowance_enabled", "Housing"],
                      ["transport_allowance_enabled", "Transport"],
                      ["responsibility_allowance_enabled", "Responsibility"],
                      ["hardship_allowance_enabled", "Hardship"],
                    ].map(([k, label]) => (
                      <label key={k} className="inline-flex items-center gap-2 text-sm cursor-pointer p-2 border border-[#E2DFD6] rounded-md hover:bg-[#FDFCFB]">
                        <input data-testid={`cs-toggle-${k}`} type="checkbox" checked={!!cs[k]} onChange={(ev) => setCs({ ...cs, [k]: ev.target.checked })} className="w-4 h-4 accent-[#0A4A1E]" />
                        {label}
                      </label>
                    ))}
                  </div>
                </div>
              </div>
              <div className="text-xs text-[#686D76] bg-[#F7F6F2] rounded-md px-3 py-2">
                Tip: changing Grade + Step auto-syncs basic salary from the step schedule.
              </div>
            </div>
          )}
        </div>

        <div className="bg-white border border-[#E2DFD6] rounded-lg p-6">
          <h3 className="font-heading text-lg font-semibold mb-4">Compensation (monthly)</h3>
          <div className="space-y-3 font-data">
            {[
              ["Basic", fmtSLE(e.basic_salary_sle)],
              ["Allowances", fmtSLE(e.allowances_sle)],
              ["Gross", fmtSLE((e.basic_salary_sle || 0) + (e.allowances_sle || 0))],
            ].map(([k, v]) => (
              <div key={k} className="flex justify-between text-sm">
                <span className="text-[#686D76]">{k}</span><span className="text-[#1A1C1E] font-medium">{v}</span>
              </div>
            ))}
          </div>
          {slip && (
            <div className="mt-5 pt-4 border-t border-[#E2DFD6] space-y-3 font-data">
              <div className="text-[10px] uppercase tracking-[0.16em] text-[#525860]">Estimated payslip</div>
              <div className="flex justify-between text-sm"><span className="text-[#686D76]">NASSIT (5%)</span><span>− {fmtSLE(slip.nassit_employee)}</span></div>
              <div className="flex justify-between text-sm"><span className="text-[#686D76]">PAYE</span><span>− {fmtSLE(slip.paye)}</span></div>
              <div className="flex justify-between text-base font-semibold pt-2 border-t border-[#E2DFD6]"><span>Net pay</span><span className="text-[#0A4A1E]">{fmtSLE(slip.net)}</span></div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function OnboardingQrModal({ qr, onClose }) {
  const print = () => window.print();
  const copyLink = () => {
    navigator.clipboard.writeText(qr.url).then(
      () => toast.success("Link copied"),
      () => toast.error("Could not copy"),
    );
  };
  const expires = new Date(qr.expires_at);
  return (
    <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4"
         onClick={onClose} data-testid="onboarding-qr-modal">
      <div onClick={(e) => e.stopPropagation()}
           className="bg-white rounded-2xl shadow-lg max-w-md w-full p-6 print:shadow-none print:p-0 print:max-w-full">
        <div className="flex items-start justify-between mb-4 print:hidden">
          <div>
            <h2 className="text-lg font-bold text-[#0A4A1E]">Onboarding QR ready</h2>
            <p className="text-[11px] text-[#525860]">Single-use · expires {expires.toLocaleDateString()}</p>
          </div>
          <button onClick={onClose} className="p-1 hover:bg-[#F1EEE6] rounded"
                  data-testid="onboarding-qr-close" aria-label="Close">
            <X className="w-5 h-5 text-[#525860]" />
          </button>
        </div>

        {/* Print-friendly sheet */}
        <div className="text-center border border-[#E2DFD6] rounded-xl p-6 space-y-3 print:border-0 print:p-2">
          <div className="text-[10px] uppercase tracking-widest text-[#525860]">Republic of Sierra Leone · SaloneHCM</div>
          <div className="text-lg font-bold text-[#0A4A1E]">Welcome to the team, {qr.employee.name.split(" ")[0]}!</div>
          <p className="text-[11px] text-[#686D76]">
            Scan this code with your phone camera to open the SaloneHCM app already signed in as{" "}
            <b>{qr.employee.email}</b>. This is a one-time link.
          </p>
          <img
            src={`data:image/png;base64,${qr.qr_png_b64}`}
            alt="Onboarding QR code"
            className="mx-auto w-56 h-56 print:w-72 print:h-72"
            data-testid="onboarding-qr-image"
          />
          <div className="text-[10px] font-data text-[#525860] break-all px-4">{qr.url}</div>
          <div className="text-[10px] text-[#A1A5AB] pt-1">
            Link expires {expires.toLocaleString()} · If lost, ask your admin to issue a new one.
          </div>
        </div>

        <div className="flex gap-2 mt-4 print:hidden">
          <button onClick={copyLink}
                  className="flex-1 text-sm border border-[#E2DFD6] py-2 rounded-lg hover:bg-[#F7F6F2]"
                  data-testid="onboarding-qr-copy-link">
            Copy link
          </button>
          <button onClick={print}
                  className="flex-1 text-sm bg-[#0A4A1E] hover:bg-[#063514] text-white py-2 rounded-lg flex items-center justify-center gap-1"
                  data-testid="onboarding-qr-print">
            <Printer className="w-4 h-4" /> Print sheet
          </button>
        </div>
      </div>
    </div>
  );
}
