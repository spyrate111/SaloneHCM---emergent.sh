import { useEffect, useState, useCallback } from "react";
import { useSearchParams } from "react-router-dom";
import api from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { toast } from "sonner";
import { Star, Plus, X, ChevronRight, ChevronDown, Award, CheckCircle2, Clock3, Download } from "lucide-react";

const STATUS_PILL = {
  pending_self: { label: "Pending self-review", color: "bg-[#FBF1DE] text-[#8B6A14]" },
  pending_manager: { label: "Pending manager", color: "bg-[#E5EEF6] text-[#26547C]" },
  completed: { label: "Completed", color: "bg-[#E6F4EC] text-[#2D7A5D]" },
  cancelled: { label: "Cancelled", color: "bg-[#EBE8E0] text-[#525860]" },
};

export default function Performance() {
  const { user } = useAuth();
  const [params] = useSearchParams();
  const isAdmin = user?.role === "admin" || user?.role === "superadmin";
  // Deep-link from digest: ?status=pending_manager → land on team tab
  const statusParam = params.get("status");
  let initialTab;
  if (statusParam === "pending_manager") {
    initialTab = isAdmin ? "team" : "mine";
  } else {
    initialTab = isAdmin ? "cycles" : "mine";
  }
  const [tab, setTab] = useState(initialTab);

  return (
    <div className="space-y-6" data-testid="performance-page">
      <div>
        <div className="text-[11px] uppercase tracking-[0.18em] text-[#525860]">Talent & Development</div>
        <h1 className="font-heading text-3xl sm:text-4xl font-bold mt-1">Performance reviews</h1>
        <p className="text-[#525860] text-sm mt-1">Structured review cycles with self-assessment, manager scoring, and employee acknowledgement.</p>
      </div>
      <div className="flex border-b border-[#E2DFD6] gap-1" role="tablist">
        {isAdmin && (
          <TabBtn active={tab === "cycles"} onClick={() => setTab("cycles")} testId="tab-cycles">
            <Award className="w-4 h-4" /> Cycles
          </TabBtn>
        )}
        <TabBtn active={tab === "mine"} onClick={() => setTab("mine")} testId="tab-mine">
          <Star className="w-4 h-4" /> My reviews
        </TabBtn>
        <TabBtn active={tab === "team"} onClick={() => setTab("team")} testId="tab-team">
          <CheckCircle2 className="w-4 h-4" /> My team
        </TabBtn>
      </div>
      {tab === "cycles" && isAdmin && <CyclesAdmin />}
      {tab === "mine" && <MyReviews />}
      {tab === "team" && <TeamReviews />}
    </div>
  );
}

function TabBtn({ active, onClick, children, testId }) {
  return (
    <button data-testid={testId} role="tab" aria-selected={active} onClick={onClick} className={`inline-flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 transition ${
      active ? "text-[#133326] border-[#133326]" : "text-[#686D76] border-transparent hover:text-[#1A1C1E]"
    }`}>{children}</button>
  );
}

function CyclesAdmin() {
  const [cycles, setCycles] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [open, setOpen] = useState(false);
  const [expanded, setExpanded] = useState(null);
  const [reviews, setReviews] = useState({});
  const [analytics, setAnalytics] = useState({});
  const [form, setForm] = useState({ name: "", period: `${new Date().getFullYear()}-H1`, description: "" });

  const load = useCallback(async () => {
    const [c, e] = await Promise.all([api.get("/performance/cycles"), api.get("/employees")]);
    setCycles(c.data); setEmployees(e.data);
  }, []);
  useEffect(() => { load(); }, [load]);

  const expand = async (cid) => {
    if (expanded === cid) { setExpanded(null); return; }
    setExpanded(cid);
    const [r, a] = await Promise.all([
      api.get(`/performance/cycles/${cid}/reviews`),
      api.get(`/performance/cycles/${cid}/analytics`),
    ]);
    setReviews((m) => ({ ...m, [cid]: r.data }));
    setAnalytics((m) => ({ ...m, [cid]: a.data }));
  };

  const submit = async (e) => {
    e.preventDefault();
    try {
      await api.post("/performance/cycles", { ...form, employee_ids: [] });
      toast.success("Review cycle started for all active employees");
      setOpen(false); load();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Could not create cycle");
    }
  };

  const downloadSummary = async (cid, period) => {
    try {
      const resp = await api.get(`/performance/cycles/${cid}/summary.pdf`, { responseType: "blob" });
      const url = URL.createObjectURL(resp.data);
      const a = document.createElement("a");
      a.href = url; a.download = `review-cycle-${period}.pdf`; a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      toast.error("Could not download summary PDF");
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="font-heading text-xl font-semibold">Review cycles</h2>
        <button data-testid="new-cycle" onClick={() => setOpen(true)} className="inline-flex items-center gap-2 bg-[#D1603D] hover:bg-[#B84F2F] text-white text-sm font-medium px-4 py-2 rounded-md">
          <Plus className="w-4 h-4" /> New cycle
        </button>
      </div>
      <div className="bg-white border border-[#E2DFD6] rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-[#F7F6F2]">
            <tr>{["", "Cycle", "Period", "Employees", "Self review", "Manager review", "Completed"].map((h) => (
              <th key={h} className="text-left text-[10px] uppercase tracking-wider text-[#525860] py-3 px-4 font-medium">{h}</th>
            ))}</tr>
          </thead>
          <tbody>
            {cycles.map((c) => {
              const p = c.progress || {};
              return (
                <CycleRowGroup key={c.id} c={c} p={p} expanded={expanded === c.id} onExpand={() => expand(c.id)} reviews={reviews[c.id] || []} analytics={analytics[c.id]} onDownloadSummary={() => downloadSummary(c.id, c.period)} />
              );
            })}
            {!cycles.length && <tr><td colSpan={7} className="py-12 text-center text-sm text-[#686D76]">No cycles yet — start one to kick off reviews for your team.</td></tr>}
          </tbody>
        </table>
      </div>

      {open && (
        <div className="fixed inset-0 bg-black/50 z-50 grid place-items-center p-4" onClick={() => setOpen(false)}>
          <form onClick={(e) => e.stopPropagation()} onSubmit={submit} className="bg-white rounded-lg w-full max-w-lg p-6">
            <div className="flex items-center justify-between mb-5">
              <h2 className="font-heading text-xl font-semibold">New review cycle</h2>
              <button type="button" onClick={() => setOpen(false)} className="p-1 text-[#686D76]"><X className="w-4 h-4" /></button>
            </div>
            <div className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-[#525860] mb-1 uppercase tracking-wider">Name</label>
                <input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="H1 2026 reviews" className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm" data-testid="cycle-name" />
              </div>
              <div>
                <label className="block text-xs font-medium text-[#525860] mb-1 uppercase tracking-wider">Period</label>
                <input required value={form.period} onChange={(e) => setForm({ ...form, period: e.target.value })} className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm font-data" data-testid="cycle-period" />
              </div>
              <div>
                <label className="block text-xs font-medium text-[#525860] mb-1 uppercase tracking-wider">Description</label>
                <textarea rows={2} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm" />
              </div>
              <div className="text-xs text-[#686D76] bg-[#F7F6F2] rounded-md px-3 py-2">
                A self-assessment row will be auto-created for each of the {employees.filter(e => e.status === "active").length} active employees.
              </div>
            </div>
            <div className="flex justify-end gap-2 mt-5">
              <button type="button" onClick={() => setOpen(false)} className="px-4 py-2 text-sm border border-[#E2DFD6] rounded-md">Cancel</button>
              <button data-testid="cycle-create" type="submit" className="px-4 py-2 text-sm bg-[#D1603D] hover:bg-[#B84F2F] text-white rounded-md">Start cycle</button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}

function CycleRowGroup({ c, p, expanded, onExpand, reviews, analytics, onDownloadSummary }) {
  const [deptFilter, setDeptFilter] = useState(null);
  const filtered = deptFilter ? reviews.filter((r) => r.department === deptFilter) : reviews;
  return (
    <>
      <tr className="border-t border-[#E2DFD6] hover:bg-[#FDFCFB] cursor-pointer" onClick={onExpand} data-testid={`cycle-row-${c.id}`}>
        <td className="py-3 px-4 text-[#686D76]">{expanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}</td>
        <td className="py-3 px-4 font-medium">{c.name}</td>
        <td className="py-3 px-4 font-data">{c.period}</td>
        <td className="py-3 px-4 font-data">{c.employee_count}</td>
        <td className="py-3 px-4 font-data text-[#8B6A14]">{p.pending_self || 0}</td>
        <td className="py-3 px-4 font-data text-[#26547C]">{p.pending_manager || 0}</td>
        <td className="py-3 px-4 font-data text-[#2D7A5D] font-semibold">{p.completed || 0}</td>
      </tr>
      {expanded && (
        <tr><td colSpan={7} className="bg-[#F7F6F2] p-0">
          <div className="px-6 py-4">
            <div className="flex justify-end mb-3">
              <button
                data-testid={`cycle-pdf-${c.id}`}
                onClick={(e) => { e.stopPropagation(); onDownloadSummary && onDownloadSummary(); }}
                className="inline-flex items-center gap-2 text-xs bg-white border border-[#E2DFD6] hover:bg-[#FDFCFB] text-[#133326] px-3 py-1.5 rounded"
              >
                <Download className="w-3.5 h-3.5" /> Download PDF summary
              </button>
            </div>
            {analytics && <AnalyticsBlock a={analytics} onDeptClick={(d) => setDeptFilter(deptFilter === d ? null : d)} active={deptFilter} />}
            <div className="flex items-center justify-between mt-5 mb-3">
              <h4 className="font-medium text-sm">
                Reviews in this cycle
                {deptFilter && (
                  <span className="ml-2 text-xs font-normal text-[#525860]">
                    · filtered by <strong className="text-[#26547C]">{deptFilter}</strong>
                    <button onClick={() => setDeptFilter(null)} className="ml-1.5 text-[#B83A3A] hover:underline" data-testid="clear-dept-filter">clear</button>
                  </span>
                )}
              </h4>
              <div className="text-xs text-[#686D76] font-data">{filtered.length} of {reviews.length}</div>
            </div>
            <table className="w-full text-xs">
              <thead><tr>{["Employee", "Department", "Self rating", "Manager rating", "Status"].map((h) => (
                <th key={h} className="text-left text-[10px] uppercase tracking-wider text-[#525860] py-2 px-3 font-medium">{h}</th>
              ))}</tr></thead>
              <tbody>
                {filtered.map((r) => (
                  <tr key={r.id} className="border-t border-[#E2DFD6]" data-testid={`review-row-${r.id}`}>
                    <td className="py-2 px-3 font-medium">{r.employee_name}</td>
                    <td className="py-2 px-3 text-[#525860]">{r.department}</td>
                    <td className="py-2 px-3 font-data">{r.self_rating ?? "—"}</td>
                    <td className="py-2 px-3 font-data">{r.manager_rating ?? "—"}</td>
                    <td className="py-2 px-3">
                      <span className={`text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-full ${STATUS_PILL[r.status]?.color}`}>{STATUS_PILL[r.status]?.label || r.status}</span>
                    </td>
                  </tr>
                ))}
                {!filtered.length && <tr><td colSpan={5} className="py-6 text-center text-[#686D76]">No reviews{deptFilter ? ` in ${deptFilter}` : ""} yet.</td></tr>}
              </tbody>
            </table>
          </div>
        </td></tr>
      )}
    </>
  );
}

function AnalyticsBlock({ a, onDeptClick, active }) {
  const distribution = a.rating_distribution || {};
  const maxN = Math.max(1, ...Object.values(distribution));
  return (
    <div className="bg-white border border-[#E2DFD6] rounded-md p-4" data-testid="cycle-analytics">
      <div className="text-[10px] uppercase tracking-[0.18em] text-[#525860]">Cycle analytics</div>
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mt-3">
        <Kpi label="Avg self" value={a.avg_self_rating?.toFixed(1) || "0.0"} sub="/5" />
        <Kpi label="Avg manager" value={a.avg_manager_rating?.toFixed(1) || "0.0"} sub="/5" tone="primary" />
        <Kpi label="Completion" value={`${Math.round((a.completion_rate || 0) * 100)}%`} sub={`${a.completed}/${a.total_reviews}`} tone="success" />
        <Kpi label="Acknowledged" value={`${Math.round((a.acknowledgement_rate || 0) * 100)}%`} sub={`${a.acknowledged}/${a.completed}`} />
        <Kpi label="Strong promo" value={a.promotion_recommendations?.strong || 0} sub="candidates" tone="warning" />
      </div>
      <div className="mt-5 grid grid-cols-1 md:grid-cols-2 gap-5">
        <div>
          <div className="text-[10px] uppercase tracking-[0.14em] text-[#525860] mb-2">Manager rating distribution</div>
          <div className="space-y-1.5">
            {[5, 4, 3, 2, 1].map((r) => {
              const n = distribution[String(r)] || 0;
              const pct = (n / maxN) * 100;
              return (
                <div key={r} className="flex items-center gap-3 text-xs">
                  <div className="w-12 font-data text-[#525860]">{r} star{r > 1 ? "s" : ""}</div>
                  <div className="flex-1 bg-[#F7F6F2] rounded h-3 overflow-hidden">
                    <div className="h-full bg-[#26547C]" style={{ width: `${pct}%` }} />
                  </div>
                  <div className="w-8 text-right font-data text-[#1A1C1E]">{n}</div>
                </div>
              );
            })}
          </div>
        </div>
        {a.department_summary?.length > 0 && (
          <div>
            <div className="text-[10px] uppercase tracking-[0.14em] text-[#525860] mb-2">By department <span className="text-[#A1A5AB] normal-case tracking-normal">(click to drill in)</span></div>
            <table className="w-full text-xs">
              <tbody>
                {a.department_summary.map((d) => (
                  <tr
                    key={d.department}
                    onClick={() => onDeptClick && onDeptClick(d.department)}
                    className={`border-b border-[#F1EEE6] cursor-pointer hover:bg-[#F1EEE6] transition ${active === d.department ? "bg-[#E5EEF6]" : ""}`}
                    data-testid={`dept-row-${d.department.replace(/\s+/g, "-").toLowerCase()}`}
                  >
                    <td className="py-1.5 font-medium">{d.department}</td>
                    <td className="py-1.5 font-data text-[#686D76]">{d.count}</td>
                    <td className="py-1.5 font-data font-medium text-right">{d.avg_rating.toFixed(1)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

function Kpi({ label, value, sub, tone }) {
  const colors = {
    primary: "text-[#26547C]",
    success: "text-[#2D7A5D]",
    warning: "text-[#8B6A14]",
  };
  return (
    <div className="bg-[#F7F6F2] rounded-md p-3 border border-[#E2DFD6]">
      <div className="text-[9px] uppercase tracking-[0.14em] text-[#686D76]">{label}</div>
      <div className={`font-heading font-bold text-xl mt-1 ${colors[tone] || "text-[#1A1C1E]"}`}>{value}</div>
      <div className="text-[10px] text-[#A1A5AB] mt-0.5 font-data">{sub}</div>
    </div>
  );
}

function MyReviews() {
  const [reviews, setReviews] = useState([]);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState({ achievements: "", challenges: "", goals_next: "", self_rating: 4 });

  const load = useCallback(async () => {
    const r = await api.get("/performance/my-reviews");
    setReviews(r.data);
  }, []);
  useEffect(() => { load(); }, [load]);

  const submitSelf = async (e) => {
    e.preventDefault();
    try {
      await api.post(`/performance/reviews/${editing.id}/self-assessment`, { ...form, self_rating: Number(form.self_rating) });
      toast.success("Self-assessment submitted");
      setEditing(null); load();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Could not submit");
    }
  };

  const acknowledge = async (rid) => {
    try {
      await api.post(`/performance/reviews/${rid}/acknowledge`, { employee_comments: "" });
      toast.success("Acknowledged");
      load();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed");
    }
  };

  return (
    <div className="space-y-4">
      <h2 className="font-heading text-xl font-semibold">My reviews</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4" data-testid="my-reviews-grid">
        {reviews.map((r) => (
          <div key={r.id} className="bg-white border border-[#E2DFD6] rounded-lg p-5">
            <div className="flex items-center justify-between gap-2 flex-wrap">
              <div>
                <div className="text-[10px] uppercase tracking-wider text-[#525860]">{r.period}</div>
                <h3 className="font-heading text-lg font-semibold mt-0.5">{r.cycle_name}</h3>
              </div>
              <span className={`text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-full ${STATUS_PILL[r.status]?.color}`}>{STATUS_PILL[r.status]?.label || r.status}</span>
            </div>
            <div className="mt-3 text-xs text-[#525860] flex gap-4 font-data">
              <div>Self <strong>{r.self_rating || "—"}</strong>/5</div>
              <div>Manager <strong>{r.manager_rating || "—"}</strong>/5</div>
            </div>
            {r.manager_score && (
              <div className="mt-2 text-xs text-[#525860] bg-[#F7F6F2] border border-[#E2DFD6] rounded-md px-3 py-2">
                <div className="font-medium text-[#1A1C1E] mb-1">Manager comments</div>
                {r.manager_score.comments || "—"}
              </div>
            )}
            <div className="mt-3 flex gap-2">
              {r.status === "pending_self" && (
                <button data-testid={`self-start-${r.id}`} onClick={() => { setEditing(r); setForm({ achievements: "", challenges: "", goals_next: "", self_rating: 4 }); }} className="text-xs bg-[#133326] hover:bg-[#0F281E] text-white px-3 py-2 rounded">
                  Start self-assessment
                </button>
              )}
              {r.status === "completed" && !r.acknowledged_at && (
                <button data-testid={`ack-${r.id}`} onClick={() => acknowledge(r.id)} className="text-xs bg-[#2D7A5D] hover:bg-[#256449] text-white px-3 py-2 rounded">
                  Acknowledge
                </button>
              )}
            </div>
          </div>
        ))}
        {!reviews.length && <div className="col-span-2 text-center py-12 text-sm text-[#686D76]">No reviews assigned yet.</div>}
      </div>

      {editing && (
        <div className="fixed inset-0 bg-black/50 z-50 grid place-items-center p-4" onClick={() => setEditing(null)}>
          <form onClick={(e) => e.stopPropagation()} onSubmit={submitSelf} className="bg-white rounded-lg w-full max-w-lg p-6">
            <div className="flex items-center justify-between mb-5">
              <h2 className="font-heading text-xl font-semibold">Self-assessment · {editing.period}</h2>
              <button type="button" onClick={() => setEditing(null)} className="p-1 text-[#686D76]"><X className="w-4 h-4" /></button>
            </div>
            <div className="space-y-3">
              {[
                ["achievements", "Key achievements this period"],
                ["challenges", "Challenges & lessons learned"],
                ["goals_next", "Goals for next period"],
              ].map(([k, l]) => (
                <div key={k}>
                  <label className="block text-xs font-medium text-[#525860] mb-1 uppercase tracking-wider">{l}</label>
                  <textarea required rows={3} value={form[k]} onChange={(e) => setForm({ ...form, [k]: e.target.value })} className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm" data-testid={`self-${k}`} />
                </div>
              ))}
              <div>
                <label className="block text-xs font-medium text-[#525860] mb-1 uppercase tracking-wider">Self rating (1–5)</label>
                <input required type="number" min="1" max="5" value={form.self_rating} onChange={(e) => setForm({ ...form, self_rating: e.target.value })} className="w-32 bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm font-data" data-testid="self-rating" />
              </div>
            </div>
            <div className="flex justify-end gap-2 mt-5">
              <button type="button" onClick={() => setEditing(null)} className="px-4 py-2 text-sm border border-[#E2DFD6] rounded-md">Cancel</button>
              <button data-testid="self-submit" type="submit" className="px-4 py-2 text-sm bg-[#D1603D] hover:bg-[#B84F2F] text-white rounded-md">Submit</button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}

function TeamReviews() {
  const [reviews, setReviews] = useState([]);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState({ manager_comments: "", manager_rating: 4, promotion_recommendation: "none", salary_action: "none" });

  const load = useCallback(async () => {
    const r = await api.get("/performance/reviews/as-manager");
    setReviews(r.data);
  }, []);
  useEffect(() => { load(); }, [load]);

  const submitScore = async (e) => {
    e.preventDefault();
    try {
      await api.post(`/performance/reviews/${editing.id}/manager-score`, { ...form, manager_rating: Number(form.manager_rating) });
      toast.success("Score saved — employee notified");
      setEditing(null); load();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Could not save");
    }
  };

  return (
    <div className="space-y-4">
      <h2 className="font-heading text-xl font-semibold">My direct reports</h2>
      <div className="bg-white border border-[#E2DFD6] rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-[#F7F6F2]">
            <tr>{["Employee", "Period", "Self rating", "Status", ""].map((h) => (
              <th key={h} className="text-left text-[10px] uppercase tracking-wider text-[#525860] py-3 px-4 font-medium">{h}</th>
            ))}</tr>
          </thead>
          <tbody>
            {reviews.map((r) => (
              <tr key={r.id} className="border-t border-[#E2DFD6]">
                <td className="py-3 px-4 font-medium">{r.employee_name}</td>
                <td className="py-3 px-4 font-data">{r.period}</td>
                <td className="py-3 px-4 font-data">{r.self_rating ?? "—"}</td>
                <td className="py-3 px-4">
                  <span className={`text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-full ${STATUS_PILL[r.status]?.color}`}>{STATUS_PILL[r.status]?.label || r.status}</span>
                </td>
                <td className="py-3 px-4 text-right">
                  {r.status === "pending_manager" && (
                    <button data-testid={`score-${r.id}`} onClick={() => setEditing(r)} className="text-xs bg-[#133326] hover:bg-[#0F281E] text-white px-3 py-1.5 rounded">
                      Score
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {!reviews.length && <tr><td colSpan={5} className="py-12 text-center text-sm text-[#686D76]">No direct-report reviews pending.</td></tr>}
          </tbody>
        </table>
      </div>

      {editing && (
        <div className="fixed inset-0 bg-black/50 z-50 grid place-items-center p-4" onClick={() => setEditing(null)}>
          <form onClick={(e) => e.stopPropagation()} onSubmit={submitScore} className="bg-white rounded-lg w-full max-w-lg p-6">
            <div className="flex items-center justify-between mb-5">
              <h2 className="font-heading text-xl font-semibold">Score · {editing.employee_name}</h2>
              <button type="button" onClick={() => setEditing(null)} className="p-1 text-[#686D76]"><X className="w-4 h-4" /></button>
            </div>
            {editing.self_assessment && (
              <div className="mb-4 bg-[#F7F6F2] border border-[#E2DFD6] rounded-md p-3 text-xs text-[#525860] space-y-2">
                <div><span className="font-medium text-[#1A1C1E]">Achievements:</span> {editing.self_assessment.achievements}</div>
                <div><span className="font-medium text-[#1A1C1E]">Challenges:</span> {editing.self_assessment.challenges}</div>
                <div><span className="font-medium text-[#1A1C1E]">Goals next:</span> {editing.self_assessment.goals_next}</div>
                <div className="text-[#26547C]"><span className="font-medium">Self-rating:</span> {editing.self_rating}/5</div>
              </div>
            )}
            <div className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-[#525860] mb-1 uppercase tracking-wider">Manager comments</label>
                <textarea required rows={3} value={form.manager_comments} onChange={(e) => setForm({ ...form, manager_comments: e.target.value })} className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm" data-testid="manager-comments" />
              </div>
              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="block text-xs font-medium text-[#525860] mb-1 uppercase tracking-wider">Rating</label>
                  <input required type="number" min="1" max="5" value={form.manager_rating} onChange={(e) => setForm({ ...form, manager_rating: e.target.value })} className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm font-data" data-testid="manager-rating" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-[#525860] mb-1 uppercase tracking-wider">Promotion</label>
                  <select value={form.promotion_recommendation} onChange={(e) => setForm({ ...form, promotion_recommendation: e.target.value })} className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm">
                    <option value="none">None</option>
                    <option value="consider">Consider</option>
                    <option value="strong">Strong</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-[#525860] mb-1 uppercase tracking-wider">Salary action</label>
                  <select value={form.salary_action} onChange={(e) => setForm({ ...form, salary_action: e.target.value })} className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm">
                    <option value="none">None</option>
                    <option value="merit">Merit increase</option>
                    <option value="promotion">Promotion adj.</option>
                  </select>
                </div>
              </div>
            </div>
            <div className="flex justify-end gap-2 mt-5">
              <button type="button" onClick={() => setEditing(null)} className="px-4 py-2 text-sm border border-[#E2DFD6] rounded-md">Cancel</button>
              <button data-testid="manager-submit" type="submit" className="px-4 py-2 text-sm bg-[#D1603D] hover:bg-[#B84F2F] text-white rounded-md inline-flex items-center gap-2">
                <Clock3 className="w-4 h-4" /> Submit score
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
