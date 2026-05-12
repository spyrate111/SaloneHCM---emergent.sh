import { useState } from "react";
import { Share2, Copy, Check, X } from "lucide-react";

export default function ShareLinkModal({ url, onClose }) {
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(url);
    } catch {
      const ta = document.createElement("textarea");
      ta.value = url;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      try { document.execCommand("copy"); } catch (e) { console.warn("clipboard fallback failed", e); }
      document.body.removeChild(ta);
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="fixed inset-0 bg-black/50 z-50 grid place-items-center p-4" onClick={onClose}>
      <div onClick={(e) => e.stopPropagation()} className="bg-white rounded-lg w-full max-w-md p-6" data-testid="share-modal">
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-heading text-xl font-semibold flex items-center gap-2"><Share2 className="w-5 h-5 text-[#26547C]" /> Shareable link</h2>
          <button onClick={onClose} className="p-1 text-[#686D76]"><X className="w-4 h-4" /></button>
        </div>
        <p className="text-sm text-[#525860] mb-4">Send this URL to anyone with admin access — they'll see the same scenario re-run against the latest employee data.</p>
        <div className="flex gap-2">
          <input readOnly value={url} onClick={(e) => e.target.select()} className="flex-1 bg-[#F7F6F2] border border-[#E2DFD6] rounded-md px-3 py-2 text-sm font-mono text-xs" />
          <button data-testid="copy-share" onClick={copy} className={`inline-flex items-center gap-1.5 px-4 py-2 text-sm rounded-md ${copied ? "bg-[#2D7A5D] text-white" : "bg-[#26547C] hover:bg-[#1D4363] text-white"}`}>
            {copied ? <><Check className="w-3.5 h-3.5" /> Copied</> : <><Copy className="w-3.5 h-3.5" /> Copy</>}
          </button>
        </div>
      </div>
    </div>
  );
}
