import { useCallback, useEffect, useState } from "react";
import { useParams, useNavigate, useSearchParams } from "react-router-dom";
import axios from "axios";
import { toast } from "sonner";
import {
  Briefcase, MapPin, Building2, Landmark, Search, ArrowLeft, CheckCircle2,
  Send, Award, Loader2, ChevronRight, Sparkles,
} from "lucide-react";

const BASE = process.env.REACT_APP_BACKEND_URL;
const publicApi = axios.create({ baseURL: `${BASE}/api`, withCredentials: false });

/** Public citizen-facing careers page. No auth required.
 *  Routes: /careers/:slug  → list  |  /careers/:slug?apply=<pid> → apply flow */
export default function PublicCareers() {
  const { slug } = useParams();
  const [params, setParams] = useSearchParams();
  const nav = useNavigate();
  const applyId = params.get("apply");

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [q, setQ] = useState("");
  const [ministry, setMinistry] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await publicApi.get(`/public/careers/${slug}`, {
        params: { q: q || undefined, ministry: ministry || undefined },
      });
      setData(r.data);
      setError(null);
    } catch (e) {
      setError(e?.response?.status === 404 ? "not_found" : "load_failed");
    } finally {
      setLoading(false);
    }
  }, [slug, q, ministry]);

  useEffect(() => { load(); }, [load]);

  if (loading && !data) {
    return (
      <div className="min-h-screen grid place-items-center bg-[#F7F6F2]">
        <Loader2 className="w-6 h-6 animate-spin text-[#0A4A1E]" />
      </div>
    );
  }

  if (error === "not_found") {
    return (
      <div className="min-h-screen grid place-items-center bg-[#F7F6F2] p-6" data-testid="careers-404">
        <div className="max-w-md text-center bg-white rounded-lg border border-[#E2DFD6] p-10">
          <div className="w-14 h-14 rounded-full bg-[#F1EEE6] grid place-items-center mx-auto">
            <Briefcase className="w-6 h-6 text-[#525860]" />
          </div>
          <h1 className="font-heading text-2xl font-bold mt-4">No public careers page</h1>
          <p className="text-sm text-[#525860] mt-2">
            The organisation &ldquo;{slug}&rdquo; hasn&rsquo;t published a public careers portal. If you&rsquo;re looking for a specific job, please contact them directly.
          </p>
        </div>
      </div>
    );
  }

  if (error === "load_failed") {
    return (
      <div className="min-h-screen grid place-items-center bg-[#F7F6F2] p-6">
        <div className="text-center">
          <p className="text-[#B84F2F] font-medium">Something went wrong loading careers.</p>
          <button onClick={load} className="mt-3 text-sm px-4 py-2 rounded-md border border-[#E2DFD6] bg-white">Try again</button>
        </div>
      </div>
    );
  }

  // Detail/apply mode
  if (applyId) {
    return <ApplyPanel slug={slug} pid={applyId} onBack={() => setParams({})} />;
  }

  return (
    <div className="min-h-screen bg-[#F7F6F2]" data-testid="careers-page">
      <Header org={data.organization} totalOpen={data.total_open} />

      <div className="max-w-[1200px] mx-auto px-4 sm:px-8 py-8">
        <FilterBar
          q={q}
          setQ={setQ}
          ministry={ministry}
          setMinistry={setMinistry}
          ministries={data.ministries}
        />

        <div className="mt-6 grid gap-3">
          {data.postings.length === 0 && (
            <div className="bg-white border border-[#E2DFD6] rounded-lg p-12 text-center" data-testid="careers-empty">
              <div className="w-12 h-12 rounded-full bg-[#F1EEE6] grid place-items-center mx-auto">
                <Briefcase className="w-5 h-5 text-[#525860]" />
              </div>
              <p className="mt-3 font-medium">No open positions match your filters.</p>
              <button onClick={() => { setQ(""); setMinistry(""); }} className="mt-3 text-sm text-[#26547C] hover:underline">
                Clear filters
              </button>
            </div>
          )}
          {data.postings.map((p) => (
            <PostingCard
              key={p.id}
              posting={p}
              onOpen={() => nav(`/careers/${slug}?apply=${p.id}`)}
            />
          ))}
        </div>

        <footer className="mt-16 pt-8 border-t border-[#E2DFD6] text-xs text-[#525860]">
          Powered by SaloneHCM — Sierra Leone Human Capital Management.
        </footer>
      </div>
    </div>
  );
}

function Header({ org, totalOpen }) {
  return (
    <header className="bg-[#0A4A1E] text-white">
      <div className="max-w-[1200px] mx-auto px-4 sm:px-8 py-10">
        <div className="text-[10px] uppercase tracking-[0.22em] text-white/60">Careers · {org.country}</div>
        <h1 className="font-heading text-3xl sm:text-4xl font-bold mt-2" data-testid="careers-org-name">
          Join {org.name}
        </h1>
        <p className="text-sm text-white/70 mt-3 max-w-xl">
          {totalOpen === 0
            ? "No open positions right now — check back soon."
            : `${totalOpen} open ${totalOpen === 1 ? "position" : "positions"} across all departments. Sierra Leonean citizens are encouraged to apply.`}
        </p>
      </div>
    </header>
  );
}

function FilterBar({ q, setQ, ministry, setMinistry, ministries }) {
  return (
    <div className="flex items-center gap-2 flex-wrap" data-testid="careers-filters">
      <div className="relative flex-1 min-w-[240px]">
        <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-[#9aa0a6]" />
        <input
          type="search"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search job titles, departments…"
          className="w-full pl-10 pr-3 h-11 bg-white border border-[#E2DFD6] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#0A4A1E]"
          data-testid="careers-search"
        />
      </div>
      {ministries.length > 0 && (
        <select
          value={ministry}
          onChange={(e) => setMinistry(e.target.value)}
          className="h-11 px-3 bg-white border border-[#E2DFD6] rounded-lg text-sm min-w-[220px]"
          data-testid="careers-ministry-filter"
        >
          <option value="">All ministries</option>
          {ministries.map((m) => <option key={m} value={m}>{m}</option>)}
        </select>
      )}
    </div>
  );
}

function PostingCard({ posting, onOpen }) {
  return (
    <button
      type="button"
      onClick={onOpen}
      data-testid={`careers-posting-${posting.id}`}
      className="w-full text-left bg-white border border-[#E2DFD6] hover:border-[#0A4A1E] rounded-lg p-5 transition group"
    >
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            {posting.source === "establishment" && (
              <span className="text-[10px] uppercase tracking-wider font-semibold px-2 py-0.5 rounded-full bg-[#E6EEF6] text-[#26547C]">
                Government post
              </span>
            )}
            <span className="text-[10px] uppercase tracking-wider text-[#525860]">
              {posting.employment_type}
            </span>
          </div>
          <h3 className="font-heading text-xl font-bold mt-1 text-[#073A16] group-hover:text-[#0A4A1E]">{posting.title}</h3>
          <div className="mt-2 flex items-center gap-4 flex-wrap text-xs text-[#525860]">
            {posting.ministry && (
              <span className="flex items-center gap-1"><Landmark className="w-3.5 h-3.5" /> {posting.ministry}</span>
            )}
            <span className="flex items-center gap-1"><Building2 className="w-3.5 h-3.5" /> {posting.department}</span>
            <span className="flex items-center gap-1"><MapPin className="w-3.5 h-3.5" /> {posting.location}</span>
            {posting.grade_code && (
              <span className="flex items-center gap-1 font-data"><Award className="w-3.5 h-3.5" /> Grade {posting.grade_code}</span>
            )}
          </div>
        </div>
        <ChevronRight className="w-5 h-5 text-[#9aa0a6] group-hover:text-[#0A4A1E]" />
      </div>
    </button>
  );
}

function ApplyPanel({ slug, pid, onBack }) {
  const [posting, setPosting] = useState(null);
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState({ name: "", email: "", phone: "", resume_summary: "" });
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(null);

  useEffect(() => {
    (async () => {
      try {
        const r = await publicApi.get(`/public/careers/${slug}/postings/${pid}`);
        setPosting(r.data.posting);
      } catch {
        toast.error("Posting not found or no longer accepting applications.");
        onBack();
      } finally {
        setLoading(false);
      }
    })();
  }, [slug, pid, onBack]);

  const submit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      const r = await publicApi.post(`/public/careers/${slug}/postings/${pid}/apply`, form);
      setSuccess(r.data);
    } catch (err) {
      const detail = err?.response?.data?.detail;
      toast.error(typeof detail === "string" ? detail : "Application failed. Please try again.");
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) return <div className="min-h-screen grid place-items-center bg-[#F7F6F2]"><Loader2 className="w-6 h-6 animate-spin text-[#0A4A1E]" /></div>;
  if (!posting) return null;

  return (
    <div className="min-h-screen bg-[#F7F6F2]" data-testid="careers-apply-page">
      <div className="bg-[#0A4A1E] text-white">
        <div className="max-w-[900px] mx-auto px-4 sm:px-8 py-6">
          <button
            onClick={onBack}
            className="inline-flex items-center gap-1.5 text-xs text-white/60 hover:text-white"
            data-testid="careers-apply-back"
          >
            <ArrowLeft className="w-3.5 h-3.5" /> Back to all positions
          </button>
        </div>
      </div>

      <div className="max-w-[900px] mx-auto px-4 sm:px-8 py-8">
        {success ? (
          <SuccessPanel result={success} onBack={onBack} />
        ) : (
          <>
            <PostingHeader posting={posting} />
            <ApplyForm
              form={form}
              setForm={setForm}
              onSubmit={submit}
              submitting={submitting}
            />
          </>
        )}
      </div>
    </div>
  );
}

function PostingHeader({ posting }) {
  return (
    <div className="bg-white border border-[#E2DFD6] rounded-lg p-6" data-testid="careers-posting-detail">
      {posting.source === "establishment" && (
        <span className="text-[10px] uppercase tracking-wider font-semibold px-2 py-0.5 rounded-full bg-[#E6EEF6] text-[#26547C]">
          Government post
        </span>
      )}
      <h1 className="font-heading text-3xl font-bold mt-2 text-[#073A16]">{posting.title}</h1>
      <div className="mt-3 flex items-center gap-4 flex-wrap text-sm text-[#525860]">
        {posting.ministry && <span className="flex items-center gap-1.5"><Landmark className="w-4 h-4" /> {posting.ministry}</span>}
        <span className="flex items-center gap-1.5"><Building2 className="w-4 h-4" /> {posting.department}</span>
        <span className="flex items-center gap-1.5"><MapPin className="w-4 h-4" /> {posting.location}</span>
        {posting.grade_code && <span className="flex items-center gap-1.5 font-data"><Award className="w-4 h-4" /> Grade {posting.grade_code}</span>}
      </div>
      {posting.description && (
        <p className="mt-5 text-sm text-[#1A1C1E] whitespace-pre-line leading-relaxed">{posting.description}</p>
      )}
    </div>
  );
}

function ApplyForm({ form, setForm, onSubmit, submitting }) {
  const upd = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));
  return (
    <form onSubmit={onSubmit} className="mt-6 bg-white border border-[#E2DFD6] rounded-lg p-6 space-y-4" data-testid="careers-apply-form">
      <div className="flex items-center gap-2">
        <Sparkles className="w-4 h-4 text-[#D1603D]" />
        <h2 className="font-heading text-xl font-bold">Apply for this position</h2>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Field label="Full name">
          <input required minLength={2} maxLength={160} value={form.name} onChange={upd("name")}
            className="w-full h-11 px-3 bg-white border border-[#E2DFD6] rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-[#0A4A1E]"
            data-testid="careers-apply-name"
          />
        </Field>
        <Field label="Email address">
          <input required type="email" value={form.email} onChange={upd("email")}
            className="w-full h-11 px-3 bg-white border border-[#E2DFD6] rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-[#0A4A1E]"
            data-testid="careers-apply-email"
          />
        </Field>
        <Field label="Phone number">
          <input required minLength={5} value={form.phone} onChange={upd("phone")}
            placeholder="+232 76 123 456"
            className="w-full h-11 px-3 bg-white border border-[#E2DFD6] rounded-md text-sm font-data focus:outline-none focus:ring-2 focus:ring-[#0A4A1E]"
            data-testid="careers-apply-phone"
          />
        </Field>
      </div>
      <Field label="Resume summary — highlight your qualifications, experience, and why you're a fit">
        <textarea required minLength={20} maxLength={4000} rows={7} value={form.resume_summary} onChange={upd("resume_summary")}
          placeholder="Share your qualifications, years of experience, key achievements, and why you want to work with us…"
          className="w-full px-3 py-2 bg-white border border-[#E2DFD6] rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-[#0A4A1E]"
          data-testid="careers-apply-resume"
        />
        <div className="text-[11px] text-[#525860] mt-1 text-right">{form.resume_summary.length}/4000</div>
      </Field>
      <div className="pt-2 border-t border-[#F1EEE6] flex items-center justify-end">
        <button
          type="submit"
          disabled={submitting}
          className="inline-flex items-center gap-2 bg-[#0A4A1E] hover:bg-[#063514] disabled:opacity-60 text-white text-sm px-5 py-2.5 rounded-md"
          data-testid="careers-apply-submit"
        >
          {submitting ? <><Loader2 className="w-4 h-4 animate-spin" /> Submitting…</> : <><Send className="w-4 h-4" /> Submit application</>}
        </button>
      </div>
    </form>
  );
}

function SuccessPanel({ result, onBack }) {
  return (
    <div className="bg-white border border-[#BFEBC8] rounded-lg p-8 text-center" data-testid="careers-apply-success">
      <div className="w-14 h-14 rounded-full bg-[#E4F7E7] grid place-items-center mx-auto">
        <CheckCircle2 className="w-6 h-6 text-[#17A035]" />
      </div>
      <h2 className="font-heading text-2xl font-bold mt-4">Application submitted</h2>
      <p className="text-sm text-[#525860] mt-2 max-w-md mx-auto">{result.message}</p>
      <div className="mt-5 inline-flex items-center gap-2 bg-[#F7F6F2] border border-[#E2DFD6] rounded-md px-4 py-2 text-xs text-[#525860]">
        Reference number: <code className="font-data text-[#0A4A1E] font-semibold" data-testid="careers-application-ref">{result.application_ref}</code>
      </div>
      <div className="mt-6">
        <button onClick={onBack} className="text-sm text-[#26547C] hover:underline">View other open positions</button>
      </div>
    </div>
  );
}

function Field({ label, children }) {
  return (
    <div>
      <label className="block text-[11px] uppercase tracking-wider text-[#525860] mb-1">{label}</label>
      {children}
    </div>
  );
}
