import { useEffect, useState, useCallback } from "react";
import api, { fmtSLE } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { Plus, Trash2, X, Heart, Shield, Wallet, Home, Bus, Smile } from "lucide-react";

const TYPE_ICON = { health: Heart, dental: Smile, pension: Wallet, life: Shield, transport: Bus, housing: Home };
const TYPE_COLOR = {
  health: "bg-[#FBE9DF] text-[#B84F2F]",
  dental: "bg-[#E5EEF6] text-[#26547C]",
  pension: "bg-[#E6F4EC] text-[#2D7A5D]",
  life: "bg-[#EBE8E0] text-[#525860]",
  transport: "bg-[#FBF1DE] text-[#8B6A14]",
  housing: "bg-[#F7E5EC] text-[#9A2A52]",
};

const empty = { name: "", type: "health", monthly_cost_sle: 0, employer_share_pct: 50, description: "" };

export default function Benefits() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [plans, setPlans] = useState([]);
  const [enrollments, setEnrollments] = useState([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(empty);

  const load = useCallback(async () => {
    const [p, e] = await Promise.all([api.get("/benefits/plans"), api.get("/benefits/enrollments")]);
    setPlans(p.data); setEnrollments(e.data);
  }, []);

  useEffect(() => { load(); }, [load]);

  const submit = async (ev) => {
    ev.preventDefault();
    await api.post("/benefits/plans", { ...form, monthly_cost_sle: Number(form.monthly_cost_sle), employer_share_pct: Number(form.employer_share_pct) });
    setOpen(false); setForm(empty); load();
  };

  const enroll = async (planId) => {
    try { await api.post("/benefits/enrollments", { plan_id: planId }); load(); }
    catch (e) { alert(e?.response?.data?.detail || "Enrollment failed"); }
  };

  const removePlan = async (id) => { await api.delete(`/benefits/plans/${id}`); load(); };
  const unenroll = async (id) => { await api.delete(`/benefits/enrollments/${id}`); load(); };

  const myEnrollments = isAdmin ? enrollments : enrollments.filter((e) => e.employee_id === user.employee_id);
  const myPlanIds = new Set(myEnrollments.map((e) => e.plan_id));

  return (
    <div className="space-y-6" data-testid="benefits-page">
      <div className="flex items-end justify-between flex-wrap gap-3">
        <div>
          <div className="text-[11px] uppercase tracking-[0.18em] text-[#525860]">Benefits Administration</div>
          <h1 className="font-heading text-3xl sm:text-4xl font-bold mt-1">Benefits</h1>
          <p className="text-[#525860] text-sm mt-1">Health, pension, life, transport, housing — plan catalog and enrollments.</p>
        </div>
        {isAdmin && (
          <button data-testid="benefits-add-plan" onClick={() => setOpen(true)} className="inline-flex items-center gap-2 bg-[#133326] hover:bg-[#0F281E] text-white text-sm font-medium px-4 py-2.5 rounded-md">
            <Plus className="w-4 h-4" /> New plan
          </button>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {plans.map((p) => {
          const Icon = TYPE_ICON[p.type] || Heart;
          const enrolled = myPlanIds.has(p.id);
          return (
            <div key={p.id} className="bg-white border border-[#E2DFD6] rounded-lg p-5 flex flex-col" data-testid={`plan-${p.id}`}>
              <div className={`w-10 h-10 rounded-md grid place-items-center ${TYPE_COLOR[p.type]}`}>
                <Icon className="w-[18px] h-[18px]" strokeWidth={1.5} />
              </div>
              <div className="mt-3 flex-1">
                <div className="text-[10px] uppercase tracking-wider text-[#525860]">{p.type}</div>
                <h3 className="font-heading text-lg font-semibold mt-0.5">{p.name}</h3>
                {p.description && <p className="text-xs text-[#686D76] mt-1.5">{p.description}</p>}
              </div>
              <div className="mt-4 pt-3 border-t border-[#F1EEE6] text-sm font-data space-y-1">
                <div className="flex justify-between"><span className="text-[#525860]">Monthly</span><span>{fmtSLE(p.monthly_cost_sle)}</span></div>
                <div className="flex justify-between"><span className="text-[#525860]">Employer share</span><span>{p.employer_share_pct}%</span></div>
              </div>
              <div className="mt-3 flex gap-2">
                {enrolled ? (
                  <span className="flex-1 inline-flex items-center justify-center text-xs bg-[#E6F4EC] text-[#2D7A5D] rounded px-3 py-2 font-medium">✓ Enrolled</span>
                ) : (
                  <button data-testid={`enroll-${p.id}`} onClick={() => enroll(p.id)} className="flex-1 inline-flex items-center justify-center text-xs bg-[#26547C] hover:bg-[#1D4363] text-white rounded px-3 py-2 font-medium">Enroll</button>
                )}
                {isAdmin && (
                  <button onClick={() => removePlan(p.id)} className="p-2 text-[#B83A3A] hover:bg-[#FBEAEA] rounded">
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>
            </div>
          );
        })}
        {!plans.length && <div className="col-span-3 text-center py-12 text-sm text-[#686D76]">No benefit plans yet.</div>}
      </div>

      <div className="bg-white border border-[#E2DFD6] rounded-lg overflow-hidden">
        <div className="px-6 py-4 border-b border-[#E2DFD6]">
          <h3 className="font-heading text-lg font-semibold">{isAdmin ? "All enrollments" : "My enrollments"}</h3>
        </div>
        <table className="w-full text-sm">
          <thead className="bg-[#F7F6F2]">
            <tr>{["Employee", "Plan", "Type", "Monthly", "Status", ""].map((h) => <th key={h} className="text-left text-[10px] uppercase tracking-wider text-[#525860] py-3 px-4 font-medium">{h}</th>)}</tr>
          </thead>
          <tbody>
            {myEnrollments.map((e) => (
              <tr key={e.id} className="border-t border-[#E2DFD6]">
                <td className="py-3 px-4">{e.employee_name}</td>
                <td className="py-3 px-4 font-medium">{e.plan_name}</td>
                <td className="py-3 px-4 capitalize">{e.plan_type}</td>
                <td className="py-3 px-4 font-data">{fmtSLE(e.monthly_cost_sle)}</td>
                <td className="py-3 px-4"><span className="text-[11px] uppercase tracking-wider px-2 py-0.5 bg-[#E6F4EC] text-[#2D7A5D] rounded-full">{e.status}</span></td>
                <td className="py-3 px-4 text-right">
                  <button onClick={() => unenroll(e.id)} className="text-xs text-[#B83A3A] hover:underline">Remove</button>
                </td>
              </tr>
            ))}
            {!myEnrollments.length && <tr><td colSpan={6} className="py-10 text-center text-sm text-[#686D76]">No enrollments yet.</td></tr>}
          </tbody>
        </table>
      </div>

      {open && (
        <div className="fixed inset-0 bg-black/50 z-50 grid place-items-center p-4" onClick={() => setOpen(false)}>
          <form onClick={(e) => e.stopPropagation()} onSubmit={submit} className="bg-white rounded-lg w-full max-w-lg p-6">
            <div className="flex items-center justify-between mb-5">
              <h2 className="font-heading text-xl font-semibold">New benefit plan</h2>
              <button type="button" onClick={() => setOpen(false)} className="p-1 text-[#686D76]"><X className="w-4 h-4" /></button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-[#525860] mb-1.5 uppercase tracking-wider">Name</label>
                <input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm" />
              </div>
              <div>
                <label className="block text-xs font-medium text-[#525860] mb-1.5 uppercase tracking-wider">Type</label>
                <select value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })} className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm">
                  {Object.keys(TYPE_ICON).map((t) => <option key={t}>{t}</option>)}
                </select>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-[#525860] mb-1.5 uppercase tracking-wider">Monthly cost (SLE)</label>
                  <input required type="number" step="0.01" value={form.monthly_cost_sle} onChange={(e) => setForm({ ...form, monthly_cost_sle: e.target.value })} className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm font-data" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-[#525860] mb-1.5 uppercase tracking-wider">Employer share %</label>
                  <input required type="number" min="0" max="100" value={form.employer_share_pct} onChange={(e) => setForm({ ...form, employer_share_pct: e.target.value })} className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm font-data" />
                </div>
              </div>
              <div>
                <label className="block text-xs font-medium text-[#525860] mb-1.5 uppercase tracking-wider">Description</label>
                <textarea rows={2} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm" />
              </div>
            </div>
            <div className="flex justify-end gap-2 mt-5">
              <button type="button" onClick={() => setOpen(false)} className="px-4 py-2 text-sm border border-[#E2DFD6] rounded-md">Cancel</button>
              <button data-testid="benefits-submit" type="submit" className="px-4 py-2 text-sm bg-[#133326] hover:bg-[#0F281E] text-white rounded-md">Save plan</button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
