import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import axios from "axios";
import { Briefcase, CheckCircle2 } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function Apply() {
  const { token } = useParams();
  const [vac, setVac] = useState(null);
  const [err, setErr] = useState("");
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);
  const [f, setF] = useState({ name: "", email: "", phone: "", cover_note: "" });
  const [cv, setCv] = useState(null);

  useEffect(() => {
    axios.get(`${API}/careers/${token}`)
      .then((r) => setVac(r.data))
      .catch(() => setErr("This vacancy link is invalid or has been removed."));
  }, [token]);

  const submit = async (e) => {
    e.preventDefault();
    if (!cv) { setErr("Please attach your CV (PDF, DOC or DOCX)."); return; }
    setBusy(true); setErr("");
    try {
      const fd = new FormData();
      Object.entries(f).forEach(([k, v]) => fd.append(k, v));
      fd.append("cv", cv);
      await axios.post(`${API}/careers/${token}/apply`, fd);
      setDone(true);
    } catch (e2) {
      setErr(e2?.response?.data?.detail || "Submission failed — please try again.");
    } finally { setBusy(false); }
  };

  const inp = "mt-1 w-full border border-[#E2DFD6] rounded-md px-3 py-2.5 text-sm bg-white";

  return (
    <div className="min-h-screen bg-[#F7F6F2] py-10 px-4" data-testid="apply-page">
      <div className="max-w-xl mx-auto">
        <div className="flex items-center gap-2 text-[#0A4A1E] font-heading font-bold text-lg mb-6">
          <Briefcase className="w-5 h-5" /> SaloneHCM Careers
        </div>
        {!vac && !err && <div className="text-sm text-[#686D76]">Loading vacancy…</div>}
        {err && !vac && <div className="bg-[#FBE9E9] text-[#B03A2E] text-sm rounded-lg p-4">{err}</div>}
        {vac && (
          <div className="bg-white border border-[#E2DFD6] rounded-xl p-6 sm:p-8">
            <div className="text-[10px] uppercase tracking-[0.16em] text-[#525860]">{vac.company_name}</div>
            <h1 className="font-heading text-2xl sm:text-3xl font-bold mt-1">{vac.title}</h1>
            <div className="text-sm text-[#686D76] mt-1">
              {vac.department}{vac.grade_level ? ` · Grade ${vac.grade_level}` : ""} · closes {vac.closing_date}
            </div>
            {vac.description && <p className="text-sm text-[#525860] mt-4 whitespace-pre-wrap">{vac.description}</p>}

            {done ? (
              <div className="mt-8 bg-[#E4F7E7] text-[#0A4A1E] rounded-lg p-5 flex items-start gap-3" data-testid="apply-success">
                <CheckCircle2 className="w-5 h-5 flex-shrink-0 mt-0.5" />
                <div>
                  <div className="font-semibold">Application received!</div>
                  <div className="text-sm mt-0.5">Thank you, {f.name}. HR will review your application and be in touch.</div>
                </div>
              </div>
            ) : !vac.accepting ? (
              <div className="mt-8 bg-[#F6EDD8] text-[#8B6A14] rounded-lg p-4 text-sm" data-testid="apply-closed">
                This vacancy is no longer accepting applications.
              </div>
            ) : (
              <form onSubmit={submit} className="mt-8 space-y-4">
                {err && <div className="bg-[#FBE9E9] text-[#B03A2E] text-sm rounded-lg p-3">{err}</div>}
                <label className="text-xs text-[#525860] block">Full name
                  <input required value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} className={inp} data-testid="apply-name" /></label>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <label className="text-xs text-[#525860] block">Email
                    <input required type="email" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} className={inp} data-testid="apply-email" /></label>
                  <label className="text-xs text-[#525860] block">Phone
                    <input value={f.phone} onChange={(e) => setF({ ...f, phone: e.target.value })} className={inp} data-testid="apply-phone" /></label>
                </div>
                <label className="text-xs text-[#525860] block">Cover note
                  <textarea rows={4} value={f.cover_note} onChange={(e) => setF({ ...f, cover_note: e.target.value })}
                    className={inp} placeholder="Why are you a great fit?" data-testid="apply-cover" /></label>
                <label className="text-xs text-[#525860] block">CV (PDF, DOC or DOCX — max 5MB)
                  <input required type="file" accept=".pdf,.doc,.docx" onChange={(e) => setCv(e.target.files?.[0] || null)}
                    className="mt-1 w-full text-sm" data-testid="apply-cv" /></label>
                <button disabled={busy}
                  className="w-full bg-[#0A4A1E] hover:bg-[#063514] text-white text-sm font-medium py-3 rounded-lg disabled:opacity-50"
                  data-testid="apply-submit">
                  {busy ? "Submitting…" : "Submit application"}
                </button>
              </form>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
