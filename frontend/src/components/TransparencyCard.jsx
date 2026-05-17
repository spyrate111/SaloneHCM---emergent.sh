import { useEffect, useState } from "react";
import api from "../lib/api";
import { toast } from "sonner";
import { Globe, Copy, Check, Eye, AlertCircle, ExternalLink } from "lucide-react";

export default function TransparencyCard() {
  const [status, setStatus] = useState(null);
  const [views, setViews] = useState(null);
  const [slug, setSlug] = useState("");
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);

  const load = async () => {
    const s = await api.get("/public/transparency/admin/status");
    setStatus(s.data);
    setSlug(s.data.slug || "");
    if (s.data.enabled) {
      try {
        const v = await api.get("/public/transparency/admin/views");
        setViews(v.data);
      } catch (e) {
        // View counters are optional metadata — log and keep the card functional.
        if (typeof console !== "undefined") console.warn("transparency view counter fetch failed", e);
      }
    }
  };
  useEffect(() => { load(); }, []);

  const toggle = async (enabled) => {
    setBusy(true);
    try {
      await api.post("/public/transparency/admin/toggle", { enabled, slug: slug || undefined });
      toast.success(enabled ? "Transparency portal published" : "Transparency portal unpublished");
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Update failed");
    } finally { setBusy(false); }
  };

  const copy = async (url) => {
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (e) {
      // Non-secure-context fallback: tell the admin to select & copy manually.
      if (typeof console !== "undefined") console.warn("Clipboard write failed", e);
      toast.error("Could not copy automatically — select the URL and copy manually.");
    }
  };

  if (!status) return null;
  const enabled = status.enabled;
  const publicUrl = status.public_url ? `${window.location.origin}${status.public_url}` : "";

  return (
    <section data-testid="transparency-card" className="bg-white border border-[#E2DFD6] rounded-xl overflow-hidden">
      <div className="px-7 py-6 border-b border-[#F1EEE6] flex items-start justify-between gap-4 flex-wrap">
        <div>
          <div className="text-[10px] uppercase tracking-[0.18em] text-[#525860]">Open Government Partnership</div>
          <h2 className="font-heading text-2xl font-bold mt-1 flex items-center gap-2">
            Public transparency portal
            {enabled
              ? <span className="text-[10px] uppercase tracking-wider font-medium px-2 py-1 rounded-full bg-[#E6F4EC] text-[#2D7A5D] inline-flex items-center gap-1"><Globe className="w-3 h-3" /> Live</span>
              : <span className="text-[10px] uppercase tracking-wider font-medium px-2 py-1 rounded-full bg-[#EBE8E0] text-[#525860]">Not published</span>}
          </h2>
          <p className="text-sm text-[#525860] mt-2 max-w-2xl">
            Publish an anonymised payroll & compliance summary to a citizen-facing URL. Shows ministry headcounts and aggregate
            financial figures — never individual employee data.
          </p>
        </div>
      </div>

      <div className="px-7 py-6 space-y-4">
        <div>
          <label className="block text-[11px] uppercase tracking-wider text-[#525860] mb-1">Public URL slug</label>
          <div className="flex items-center gap-2 flex-wrap">
            <code className="text-xs bg-[#F7F6F2] border border-[#E2DFD6] rounded px-2 py-1 font-data">/transparency/</code>
            <input
              data-testid="transparency-slug"
              value={slug}
              onChange={(e) => setSlug(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, "").slice(0, 60))}
              placeholder="government-of-sierra-leone"
              className="flex-1 max-w-xs bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm font-data"
            />
          </div>
        </div>

        {enabled && publicUrl && (
          <div className="bg-[#F7F6F2] border border-[#E2DFD6] rounded-md p-4 space-y-3" data-testid="transparency-live-block">
            <div className="text-[11px] uppercase tracking-wider text-[#525860]">Citizen-facing URL</div>
            <div className="flex items-center gap-2 flex-wrap">
              <code className="text-sm bg-white border border-[#E2DFD6] rounded px-3 py-2 font-data flex-1 min-w-0 truncate">{publicUrl}</code>
              <button onClick={() => copy(publicUrl)} className="inline-flex items-center gap-1.5 text-xs bg-white border border-[#E2DFD6] hover:bg-[#F1EEE6] text-[#26547C] px-3 py-2 rounded-md">
                {copied ? <><Check className="w-3.5 h-3.5" /> Copied</> : <><Copy className="w-3.5 h-3.5" /> Copy</>}
              </button>
              <a href={publicUrl} target="_blank" rel="noreferrer" data-testid="transparency-open" className="inline-flex items-center gap-1.5 text-xs bg-[#26547C] hover:bg-[#1D4363] text-white px-3 py-2 rounded-md">
                <ExternalLink className="w-3.5 h-3.5" /> Open
              </a>
            </div>
            {views && (
              <div className="flex items-center gap-4 text-xs text-[#525860]">
                <div className="flex items-center gap-1.5">
                  <Eye className="w-3.5 h-3.5" />
                  <span className="font-data font-medium text-[#1A1C1E]">{views.total_views}</span> total citizen views
                </div>
                <div>· <span className="font-data font-medium text-[#1A1C1E]">{views.last_7d}</span> in last 7 days</div>
              </div>
            )}
          </div>
        )}

        {!enabled && (
          <div className="text-xs bg-[#FBF1DE] border border-[#E8D5A2] text-[#8B6A14] rounded-md px-3 py-2 inline-flex items-center gap-1.5">
            <AlertCircle className="w-4 h-4" />
            Publishing makes payroll summaries publicly accessible — citizens won't need an account to view.
          </div>
        )}

        <div className="flex items-center gap-2 pt-2">
          {!enabled ? (
            <button
              data-testid="transparency-publish"
              disabled={busy || !slug}
              onClick={() => toggle(true)}
              className="inline-flex items-center gap-2 bg-[#133326] hover:bg-[#0F281E] text-white text-sm px-4 py-2.5 rounded-md disabled:opacity-60"
            >
              <Globe className="w-4 h-4" /> Publish portal
            </button>
          ) : (
            <button
              data-testid="transparency-unpublish"
              disabled={busy}
              onClick={() => toggle(false)}
              className="text-sm text-[#B83A3A] hover:bg-[#FBEAEA] border border-[#E2DFD6] rounded-md px-3 py-2 disabled:opacity-60"
            >
              Unpublish portal
            </button>
          )}
          {enabled && (
            <button
              data-testid="transparency-update-slug"
              disabled={busy || !slug || slug === status.slug}
              onClick={() => toggle(true)}
              className="text-sm bg-white border border-[#E2DFD6] hover:bg-[#F7F6F2] rounded-md px-3 py-2 disabled:opacity-60"
            >
              Update slug
            </button>
          )}
        </div>
      </div>
    </section>
  );
}
