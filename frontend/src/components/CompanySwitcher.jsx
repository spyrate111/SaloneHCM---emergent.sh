import { useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext";
import api, { setToken } from "../lib/api";
import { toast } from "sonner";
import { ArrowRightLeft, ChevronDown } from "lucide-react";

export default function CompanySwitcher() {
  const { user, refetch } = useAuth();
  const [companies, setCompanies] = useState([]);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.get("/admin/companies").then((r) => setCompanies(r.data)).catch(() => {});
  }, []);

  const switchTo = async (cid) => {
    if (cid === user?.company_id) { setOpen(false); return; }
    setBusy(true);
    try {
      const r = await api.post(`/admin/companies/${cid}/switch`);
      setToken(r.data.token);
      await refetch();
      toast.success(`Switched to ${r.data.company.name}`);
      setOpen(false);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Switch failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="relative" data-testid="company-switcher">
      <button
        onClick={() => setOpen((v) => !v)}
        className="inline-flex items-center gap-1.5 text-xs font-medium border border-[#E2DFD6] rounded-md px-2.5 py-1.5 hover:bg-[#F7F6F2]"
        data-testid="company-switcher-toggle"
      >
        <ArrowRightLeft className="w-3.5 h-3.5 text-[#525860]" strokeWidth={1.7} />
        Switch tenant
        <ChevronDown className={`w-3.5 h-3.5 text-[#525860] transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <div className="absolute top-full mt-2 left-0 w-72 bg-white border border-[#E2DFD6] rounded-lg shadow-lg z-30 overflow-hidden" data-testid="company-switcher-menu">
          <div className="px-4 py-2.5 text-[10px] uppercase tracking-wider text-[#525860] border-b border-[#F1EEE6] bg-[#F7F6F2]">
            Tenants ({companies.length})
          </div>
          <div className="max-h-72 overflow-y-auto">
            {companies.map((c) => (
              <CompanyRow key={c.id} c={c} active={c.id === user?.company_id} busy={busy} onClick={() => switchTo(c.id)} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function CompanyRow({ c, active, busy, onClick }) {
  return (
    <button
      disabled={busy}
      onClick={onClick}
      data-testid={`switcher-item-${c.id}`}
      className={`w-full text-left px-4 py-2.5 text-sm hover:bg-[#F7F6F2] flex items-center justify-between gap-2 ${active ? "bg-[#E6F4EC]" : ""}`}
    >
      <div className="min-w-0">
        <div className="font-medium truncate">{c.name}</div>
        <div className="text-[10px] uppercase tracking-wider text-[#686D76]">{c.tier} · {c.active_headcount} active</div>
      </div>
      {active && (
        <span className="text-[9px] uppercase tracking-widest font-semibold bg-[#133326] text-white px-1.5 py-0.5 rounded-full">
          Active
        </span>
      )}
    </button>
  );
}
