import { useEffect, useState } from "react";
import api from "../lib/api";
import { toast } from "sonner";
import { PenLine, Minus, Plus } from "lucide-react";

// Superadmin-only card: dial how many distinct MoF signatures a payroll run
// needs before it flips to 'approved' (backend PUT is superadmin-gated too).
export default function MoFConfigCard() {
  const [required, setRequired] = useState(null);
  const [saved, setSaved] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.get("/civil-service/mof/config").then((r) => {
      setRequired(r.data.signatures_required);
      setSaved(r.data.signatures_required);
    }).catch(() => {});
  }, []);

  if (required === null) return null;

  const save = async () => {
    setBusy(true);
    try {
      await api.put("/civil-service/mof/config", { signatures_required: required });
      setSaved(required);
      toast.success(`MoF approval now requires ${required} signature${required > 1 ? "s" : ""}`);
    } catch (e) {
      const d = e?.response?.data?.detail;
      toast.error(typeof d === "string" ? d : "Update failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="bg-white border border-[#E2DFD6] rounded-lg p-5" data-testid="mof-config-card">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div className="flex items-start gap-3">
          <div className="w-9 h-9 rounded-md bg-[#F1EEE6] grid place-items-center shrink-0">
            <PenLine className="w-4 h-4 text-[#133326]" strokeWidth={1.6} />
          </div>
          <div>
            <h3 className="font-heading text-sm font-semibold">Multi-signature MoF approval</h3>
            <p className="text-xs text-[#525860] mt-0.5 max-w-md">
              Distinct MoF approver signatures required before a payroll run is approved.
              Higher values prevent unilateral sign-off. Superadmin only.
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center border border-[#E2DFD6] rounded-md overflow-hidden">
            <button data-testid="mof-config-minus" onClick={() => setRequired((n) => Math.max(1, n - 1))}
              disabled={required <= 1}
              className="px-2.5 py-2 hover:bg-[#F7F6F2] disabled:opacity-30">
              <Minus className="w-3.5 h-3.5" />
            </button>
            <span data-testid="mof-config-value" className="w-10 text-center font-data font-bold text-lg">{required}</span>
            <button data-testid="mof-config-plus" onClick={() => setRequired((n) => Math.min(5, n + 1))}
              disabled={required >= 5}
              className="px-2.5 py-2 hover:bg-[#F7F6F2] disabled:opacity-30">
              <Plus className="w-3.5 h-3.5" />
            </button>
          </div>
          <button data-testid="mof-config-save" onClick={save} disabled={busy || required === saved}
            className="text-sm bg-[#133326] hover:bg-[#0F281E] text-white px-4 py-2 rounded-md disabled:opacity-40">
            {required === saved ? "Saved" : "Save"}
          </button>
        </div>
      </div>
    </div>
  );
}
