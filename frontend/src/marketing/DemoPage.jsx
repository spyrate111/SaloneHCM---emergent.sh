import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  ArrowRight, ArrowLeft, CheckCircle2, ShieldCheck, Phone, Mail,
  Calculator, Users, ShieldAlert, Sparkles, Award, Wallet, Landmark, GraduationCap, Smile, Lock,
} from "lucide-react";
import MarketingLayout from "./MarketingLayout";
import api from "../lib/api";

const INDUSTRIES = [
  { value: "ngo", label: "NGO / Development" },
  { value: "mining", label: "Mining & Energy" },
  { value: "banking", label: "Banking & Finance" },
  { value: "telecom", label: "Telecommunications" },
  { value: "government", label: "Government / MDA" },
  { value: "manufacturing", label: "Manufacturing" },
  { value: "retail", label: "Retail / Hospitality" },
  { value: "other", label: "Other" },
];

const SIZE_BUCKETS = [
  { value: "1-9",     label: "1–9", desc: "Just getting started" },
  { value: "10-49",   label: "10–49", desc: "Small but growing" },
  { value: "50-249",  label: "50–249", desc: "Mid-market" },
  { value: "250-999", label: "250–999", desc: "Enterprise" },
  { value: "1000+",   label: "1,000+", desc: "Large enterprise / MDA" },
];

const TOPICS = [
  { value: "payroll",       icon: Calculator,     label: "Payroll Engine",       blurb: "PAYE, NASSIT, GST in one click" },
  { value: "hr",            icon: Users,          label: "HR & Employees",       blurb: "Records, leave, attendance" },
  { value: "compliance",    icon: ShieldCheck,    label: "Compliance & Tax",     blurb: "NRA filings, MoF audit-ready" },
  { value: "ai",            icon: Sparkles,       label: "AI Assistant",         blurb: "Action-mode admin chat" },
  { value: "civil_service", icon: Award,          label: "Civil Service",        blurb: "Grade/step, ghost-worker audit" },
  { value: "ifmis",         icon: Landmark,       label: "IFMIS Integration",    blurb: "Bank file + reconciliation" },
  { value: "loans",         icon: Wallet,         label: "Loans & Advances",     blurb: "Payroll-deducted lifecycle" },
  { value: "talent",        icon: GraduationCap,  label: "Talent & Performance", blurb: "ATS, training, reviews" },
];

const TRUST_BADGES = [
  { slug: "nra",      icon: ShieldCheck, label: "NRA-certified",      tone: "text-[#1f6f55]" },
  { slug: "wca",      icon: Lock,        label: "Data hosted in WCA", tone: "text-[#0F2C24]" },
  { slug: "nassit",   icon: Award,       label: "NASSIT-registered",  tone: "text-[#E07B4A]" },
  { slug: "iso27001", icon: ShieldAlert, label: "ISO-27001 aligned",  tone: "text-[#5a4FCF]" },
];

const TESTIMONIALS = [
  {
    quote: "9 minutes to file our last NRA PAYE return. And it was right.",
    name: "Aminata Kamara",
    role: "Director of Finance, Freetown Logistics",
  },
  {
    quote: "Ghost-worker audits used to take a quarter. Now they take a morning.",
    name: "Mohamed Sesay",
    role: "Permanent Secretary, Ministry of Works",
  },
];

const STEPS = ["You", "Your team", "Your goals"];

export default function DemoPage() {
  const nav = useNavigate();
  const [step, setStep] = useState(0); // 0..2 then 3 = success
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [form, setForm] = useState({
    name: "", email: "", phone: "",
    company: "", industry: "", size: "",
    topics: [],
    message: "",
  });

  // Hydrate from landing-page "Solution Wizard" handoff if present
  useEffect(() => {
    try {
      const raw = sessionStorage.getItem("salonehcm_lead");
      if (raw) {
        const parsed = JSON.parse(raw);
        const known = new Set(TOPICS.map((t) => t.value));
        const hydratedTopic = known.has(parsed.interest) ? [parsed.interest] : [];
        setForm((f) => ({
          ...f,
          size: bucketFromEmployees(parsed.employees) || f.size,
          topics: hydratedTopic.length ? hydratedTopic : f.topics,
        }));
      }
    } catch (err) {
      console.debug("[DemoPage] lead hydration skipped:", err?.message || err);
    }
  }, []);

  const update = (k) => (e) => {
    const v = e?.target ? e.target.value : e;
    setForm((f) => ({ ...f, [k]: v }));
  };

  const toggleTopic = (val) => {
    setForm((f) => ({
      ...f,
      topics: f.topics.includes(val) ? f.topics.filter((t) => t !== val) : [...f.topics, val],
    }));
  };

  const canAdvance = useMemo(() => {
    if (step === 0) return form.name.trim().length >= 2 && /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(form.email);
    if (step === 1) return form.company.trim().length >= 2 && !!form.industry && !!form.size;
    if (step === 2) return form.topics.length >= 1;
    return true;
  }, [step, form]);

  const submit = async () => {
    setSubmitting(true);
    setError("");
    try {
      const payload = {
        name: form.name.trim(),
        email: form.email.trim().toLowerCase(),
        phone: form.phone.trim() || null,
        company: form.company.trim(),
        industry: form.industry,
        size: form.size,
        topics: form.topics,
        message: form.message.trim() || null,
      };
      await api.post("/marketing/demo-requests", payload);
      setStep(3);
    } catch (err) {
      const detail = err?.response?.data?.detail;
      setError(typeof detail === "string" ? detail : "We couldn't submit your request. Please try again or call sales.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <MarketingLayout>
      <section data-testid="demo-page" className="bg-gradient-to-b from-[#FAF8F2] to-white">
        <div className="max-w-[1280px] mx-auto px-6 lg:px-10 py-12 lg:py-16">
          <header className="max-w-[820px]">
            <button
              type="button"
              onClick={() => nav("/")}
              className="inline-flex items-center gap-1 text-[12px] text-[#525860] hover:text-[#C02719] mb-3"
              data-testid="demo-back-to-home"
            >
              <ArrowLeft className="w-3.5 h-3.5" /> Back to home
            </button>
            <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-[#C02719]">Experience SaloneHCM</p>
            <h1 className="mt-2 text-[36px] sm:text-[48px] font-extrabold text-[#0F2C24] leading-[1.05]">
              {step < 3
                ? <>Get a personalized <span className="text-[#C02719]">HR &amp; payroll</span> demo.</>
                : <>You&rsquo;re in. We&rsquo;ll meet you on the other side.</>}
            </h1>
            <p className="mt-3 text-[16px] sm:text-[17px] text-[#374049] max-w-[720px] leading-relaxed">
              {step < 3
                ? <>Three quick questions and a SaloneHCM specialist will show you exactly how we&rsquo;d run payroll for your team &mdash; tailored to NRA PAYE, NASSIT, and your industry&rsquo;s allowance presets.</>
                : <>A specialist will reach out within <strong className="text-[#0F2C24]">24 business hours</strong> with a tailored demo slot. In the meantime, jump into the sandbox or grab a sample payslip below.</>}
            </p>
          </header>

          <div className="grid lg:grid-cols-12 gap-8 lg:gap-10 mt-10">
            {/* Left: Wizard */}
            <div className="lg:col-span-7">
              <div className="bg-white border border-[#EAE7DF] rounded-2xl shadow-sm overflow-hidden">
                {step < 3 && <ProgressBar step={step} />}
                <div className="p-6 sm:p-8">
                  {step === 0 && (
                    <StepYou form={form} update={update} />
                  )}
                  {step === 1 && (
                    <StepTeam form={form} update={update} />
                  )}
                  {step === 2 && (
                    <StepGoals form={form} toggleTopic={toggleTopic} update={update} />
                  )}
                  {step === 3 && (
                    <StepSuccess form={form} />
                  )}

                  {error && step < 3 && (
                    <div className="mt-4 text-[13px] text-[#C02719]" data-testid="demo-error">{error}</div>
                  )}

                  {step < 3 && (
                    <div className="mt-7 flex items-center justify-between gap-3 border-t border-[#F1EEE6] pt-5">
                      <button
                        type="button"
                        onClick={() => setStep((s) => Math.max(0, s - 1))}
                        disabled={step === 0}
                        className="inline-flex items-center gap-1.5 text-[13px] text-[#525860] hover:text-[#0F2C24] disabled:opacity-40 disabled:cursor-not-allowed"
                        data-testid="demo-back-button"
                      >
                        <ArrowLeft className="w-4 h-4" /> Back
                      </button>
                      <div className="flex items-center gap-3">
                        <span className="text-[11px] text-[#686D76]" data-testid="demo-step-indicator">Step {step + 1} of 3</span>
                        {step < 2 ? (
                          <button
                            type="button"
                            onClick={() => setStep((s) => Math.min(2, s + 1))}
                            disabled={!canAdvance}
                            className={`inline-flex items-center gap-1.5 px-5 h-11 text-[14px] font-bold rounded-full transition-colors ${
                              canAdvance
                                ? "bg-[#C02719] text-white hover:bg-[#9c1f14]"
                                : "bg-[#EAE7DF] text-[#9aa0a6] cursor-not-allowed"
                            }`}
                            data-testid="demo-next-button"
                          >
                            Continue <ArrowRight className="w-4 h-4" />
                          </button>
                        ) : (
                          <button
                            type="button"
                            onClick={submit}
                            disabled={!canAdvance || submitting}
                            className={`inline-flex items-center gap-1.5 px-5 h-11 text-[14px] font-bold rounded-full transition-colors ${
                              canAdvance && !submitting
                                ? "bg-[#C02719] text-white hover:bg-[#9c1f14]"
                                : "bg-[#EAE7DF] text-[#9aa0a6] cursor-not-allowed"
                            }`}
                            data-testid="demo-submit-button"
                          >
                            {submitting ? "Submitting…" : (<>Book my demo <ArrowRight className="w-4 h-4" /></>)}
                          </button>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              </div>

              <p className="mt-3 text-[11px] text-[#686D76] leading-relaxed">
                By submitting, you agree to receive a follow-up from SaloneHCM. We never share your details. See our{" "}
                <a className="underline hover:no-underline" href="/#footer">Privacy Policy</a>.
              </p>
            </div>

            {/* Right rail */}
            <aside className="lg:col-span-5 space-y-5" data-testid="demo-right-rail">
              <div className="bg-[#0F2C24] text-white rounded-2xl p-6 sm:p-7 relative overflow-hidden">
                <div className="absolute -right-12 -top-12 w-44 h-44 rounded-full bg-[#E07B4A] opacity-20 blur-2xl"></div>
                <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-[#E07B4A]">Why SaloneHCM</p>
                <ul className="mt-3 space-y-3">
                  {["NRA PAYE & NASSIT computed automatically",
                    "Bulk SMS payslips via Twilio +232",
                    "AI Assistant in English & Krio",
                    "Stripe + local bank-transfer billing"].map((b) => (
                    <li key={b} className="flex items-start gap-2.5 text-[14px] leading-snug">
                      <CheckCircle2 className="w-4 h-4 text-[#E07B4A] flex-none mt-0.5" /> {b}
                    </li>
                  ))}
                </ul>
                <div className="mt-5 pt-5 border-t border-white/15">
                  <p className="text-[11px] uppercase tracking-[0.14em] text-white/65">Prefer to talk?</p>
                  <a href="tel:+23230000000" className="mt-1.5 flex items-center gap-2 text-[18px] font-extrabold hover:text-[#E07B4A]" data-testid="demo-rail-phone">
                    <Phone className="w-4 h-4" /> +232 30 000 000
                  </a>
                  <a href="mailto:hello@salonehcm.sl" className="mt-1.5 flex items-center gap-2 text-[13px] text-white/80 hover:text-white" data-testid="demo-rail-email">
                    <Mail className="w-3.5 h-3.5" /> hello@salonehcm.sl
                  </a>
                </div>
              </div>

              <div className="bg-white border border-[#EAE7DF] rounded-2xl p-6">
                <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-[#C02719]">Trust &amp; security</p>
                <div className="mt-3 grid grid-cols-2 gap-3">
                  {TRUST_BADGES.map((b) => {
                    const Icon = b.icon;
                    return (
                      <div key={b.label} className="bg-[#FAF8F2] rounded-lg p-3 flex items-center gap-2.5" data-testid={`trust-${b.slug}`}>
                        <Icon className={`w-5 h-5 ${b.tone}`} />
                        <span className="text-[12px] font-semibold text-[#0F2C24] leading-tight">{b.label}</span>
                      </div>
                    );
                  })}
                </div>
              </div>

              {TESTIMONIALS.map((t) => (
                <figure key={t.name} className="bg-white border border-[#EAE7DF] rounded-2xl p-6 relative" data-testid={`rail-quote-${t.name.split(" ")[0].toLowerCase()}`}>
                  <Smile className="w-5 h-5 text-[#E07B4A] mb-2" />
                  <blockquote className="text-[14px] text-[#0F2C24] leading-relaxed">&ldquo;{t.quote}&rdquo;</blockquote>
                  <figcaption className="mt-3 text-[12px]">
                    <div className="font-bold text-[#0F2C24]">{t.name}</div>
                    <div className="text-[#525860]">{t.role}</div>
                  </figcaption>
                </figure>
              ))}
            </aside>
          </div>
        </div>
      </section>
    </MarketingLayout>
  );
}

// --- helpers and sub-steps ---

function bucketFromEmployees(n) {
  const v = Number(n);
  if (!v) return "";
  if (v < 10) return "1-9";
  if (v < 50) return "10-49";
  if (v < 250) return "50-249";
  if (v < 1000) return "250-999";
  return "1000+";
}

function ProgressBar({ step }) {
  return (
    <div className="bg-[#FAF8F2] border-b border-[#EAE7DF] px-6 sm:px-8 py-4" data-testid="demo-progress-bar">
      <ol className="flex items-center gap-2 sm:gap-4">
        {STEPS.map((label, i) => {
          const active = i === step;
          const done = i < step;
          return (
            <li key={label} className="flex items-center gap-2 sm:gap-3 flex-1" data-testid={`demo-step-${i}`}>
              <div className={`w-7 h-7 rounded-full grid place-items-center text-[11px] font-bold border ${
                done ? "bg-[#1f6f55] border-[#1f6f55] text-white"
                : active ? "bg-[#C02719] border-[#C02719] text-white"
                : "bg-white border-[#EAE7DF] text-[#9aa0a6]"
              }`}>
                {done ? <CheckCircle2 className="w-4 h-4" /> : i + 1}
              </div>
              <div className="flex-1 hidden sm:block">
                <div className={`text-[12.5px] font-semibold ${active ? "text-[#0F2C24]" : done ? "text-[#1f6f55]" : "text-[#9aa0a6]"}`}>{label}</div>
              </div>
              {i < STEPS.length - 1 && (
                <div className={`hidden sm:block h-px flex-1 ${done ? "bg-[#1f6f55]" : "bg-[#EAE7DF]"}`}></div>
              )}
            </li>
          );
        })}
      </ol>
    </div>
  );
}

function StepYou({ form, update }) {
  return (
    <div data-testid="demo-step-you">
      <h2 className="text-[20px] sm:text-[24px] font-extrabold text-[#0F2C24]">Who are you?</h2>
      <p className="mt-1.5 text-[14px] text-[#525860]">We&rsquo;ll only use this to send your tailored demo.</p>
      <div className="mt-6 grid sm:grid-cols-2 gap-4">
        <Field label="Full name">
          <input required value={form.name} onChange={update("name")} placeholder="e.g. Aminata Kamara"
            className="w-full h-11 px-3 border border-[#EAE7DF] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#0F2C24]"
            data-testid="demo-input-name" />
        </Field>
        <Field label="Work email">
          <input required type="email" value={form.email} onChange={update("email")} placeholder="you@company.sl"
            className="w-full h-11 px-3 border border-[#EAE7DF] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#0F2C24]"
            data-testid="demo-input-email" />
        </Field>
        <Field label="Phone (optional)" colSpan="sm:col-span-2">
          <input type="tel" value={form.phone} onChange={update("phone")} placeholder="+232 30 000 000"
            className="w-full h-11 px-3 border border-[#EAE7DF] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#0F2C24]"
            data-testid="demo-input-phone" />
        </Field>
      </div>
    </div>
  );
}

function StepTeam({ form, update }) {
  return (
    <div data-testid="demo-step-team">
      <h2 className="text-[20px] sm:text-[24px] font-extrabold text-[#0F2C24]">Tell us about your team.</h2>
      <p className="mt-1.5 text-[14px] text-[#525860]">We&rsquo;ll match you to the right plan and the right specialist.</p>
      <div className="mt-6 grid sm:grid-cols-2 gap-4">
        <Field label="Company / Organization" colSpan="sm:col-span-2">
          <input required value={form.company} onChange={update("company")} placeholder="e.g. Freetown Logistics Ltd."
            className="w-full h-11 px-3 border border-[#EAE7DF] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#0F2C24]"
            data-testid="demo-input-company" />
        </Field>
        <Field label="Industry">
          <select required value={form.industry} onChange={update("industry")}
            className="w-full h-11 px-3 border border-[#EAE7DF] rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-[#0F2C24]"
            data-testid="demo-select-industry">
            <option value="" disabled>Select industry</option>
            {INDUSTRIES.map((i) => <option key={i.value} value={i.value}>{i.label}</option>)}
          </select>
        </Field>
      </div>
      <div className="mt-5">
        <label className="text-[12px] font-bold uppercase tracking-[0.1em] text-[#525860]"># of employees</label>
        <div className="mt-2 grid grid-cols-2 sm:grid-cols-5 gap-2">
          {SIZE_BUCKETS.map((b) => {
            const active = form.size === b.value;
            return (
              <button
                key={b.value} type="button" onClick={() => update("size")(b.value)}
                className={`text-left px-3 py-2.5 rounded-lg border transition-all ${
                  active
                    ? "border-[#C02719] bg-[#FFE9E5] ring-2 ring-[#C02719]/15"
                    : "border-[#EAE7DF] bg-white hover:border-[#0F2C24]"
                }`}
                data-testid={`demo-size-${b.value}`}
              >
                <div className={`text-[14px] font-extrabold ${active ? "text-[#C02719]" : "text-[#0F2C24]"}`}>{b.label}</div>
                <div className="text-[10.5px] text-[#525860] mt-0.5 leading-tight">{b.desc}</div>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function StepGoals({ form, toggleTopic, update }) {
  return (
    <div data-testid="demo-step-goals">
      <h2 className="text-[20px] sm:text-[24px] font-extrabold text-[#0F2C24]">What do you want to see?</h2>
      <p className="mt-1.5 text-[14px] text-[#525860]">Pick everything that sounds useful &mdash; we&rsquo;ll tailor the demo around it.</p>
      <div className="mt-6 grid sm:grid-cols-2 gap-3">
        {TOPICS.map((t) => {
          const Icon = t.icon;
          const active = form.topics.includes(t.value);
          return (
            <button
              key={t.value} type="button" onClick={() => toggleTopic(t.value)}
              className={`text-left p-4 rounded-xl border transition-all relative ${
                active
                  ? "border-[#C02719] bg-[#FFE9E5] ring-2 ring-[#C02719]/15"
                  : "border-[#EAE7DF] bg-white hover:border-[#0F2C24]"
              }`}
              data-testid={`demo-topic-${t.value}`}
            >
              <div className="flex items-start gap-3">
                <div className={`w-9 h-9 rounded-lg grid place-items-center flex-none ${active ? "bg-[#C02719] text-white" : "bg-[#FAF8F2] text-[#0F2C24]"}`}>
                  <Icon className="w-4 h-4" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className={`text-[14px] font-extrabold ${active ? "text-[#C02719]" : "text-[#0F2C24]"}`}>{t.label}</div>
                  <div className="text-[11.5px] text-[#525860] mt-0.5 leading-snug">{t.blurb}</div>
                </div>
                <div className={`w-5 h-5 rounded-full border-2 grid place-items-center flex-none ${active ? "border-[#C02719] bg-[#C02719]" : "border-[#EAE7DF]"}`}>
                  {active && <CheckCircle2 className="w-3 h-3 text-white" strokeWidth={3} />}
                </div>
              </div>
            </button>
          );
        })}
      </div>
      <div className="mt-6">
        <Field label="Anything specific we should know? (optional)">
          <textarea rows={3} value={form.message} onChange={update("message")}
            placeholder="e.g. We're switching off a manual ledger, need help with NASSIT back-filings…"
            className="w-full px-3 py-2 border border-[#EAE7DF] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#0F2C24]"
            data-testid="demo-input-message"
          />
        </Field>
      </div>
    </div>
  );
}

function StepSuccess({ form }) {
  return (
    <div className="text-center py-6" data-testid="demo-step-success">
      <div className="w-16 h-16 rounded-full bg-[#E6F2EC] grid place-items-center mx-auto">
        <CheckCircle2 className="w-8 h-8 text-[#1f6f55]" />
      </div>
      <h2 className="mt-5 text-[26px] sm:text-[32px] font-extrabold text-[#0F2C24] leading-tight">
        Demo request received, {form.name.split(" ")[0] || "there"}.
      </h2>
      <p className="mt-2 text-[15px] text-[#525860] max-w-[520px] mx-auto leading-relaxed">
        A SaloneHCM specialist will reach you at <strong className="text-[#0F2C24]">{form.email}</strong>{form.phone ? <> or <strong className="text-[#0F2C24]">{form.phone}</strong></> : null}{" "}within <strong className="text-[#0F2C24]">24 business hours</strong>.
      </p>
      <div className="mt-7 grid sm:grid-cols-3 gap-3 text-left">
        <NextStepCard title="Pick a time" desc="Open the calendar and grab any 30-minute slot." cta="Open calendar" href="https://calendly.com/" />
        <NextStepCard title="Sample payslip" desc="See exactly what your team will receive each month." cta="Download PDF" href="#" />
        <NextStepCard title="Talk now" desc="Sales is online during Africa/Freetown hours." cta="Call sales" href="tel:+23230000000" />
      </div>
    </div>
  );
}

function NextStepCard({ title, desc, cta, href }) {
  return (
    <a href={href} className="block bg-[#FAF8F2] border border-[#EAE7DF] rounded-xl p-4 hover:border-[#0F2C24] hover:shadow-sm transition-all group" data-testid={`next-${title.toLowerCase().replace(/\s+/g, "-")}`}>
      <div className="text-[14px] font-extrabold text-[#0F2C24]">{title}</div>
      <div className="text-[12px] text-[#525860] mt-1 leading-snug">{desc}</div>
      <div className="mt-2 inline-flex items-center gap-1 text-[12.5px] font-bold text-[#C02719] group-hover:gap-2 transition-all">
        {cta} <ArrowRight className="w-3.5 h-3.5" />
      </div>
    </a>
  );
}

function Field({ label, children, colSpan = "" }) {
  return (
    <div className={colSpan}>
      <label className="block text-[12px] font-bold uppercase tracking-[0.1em] text-[#525860] mb-1.5">{label}</label>
      {children}
    </div>
  );
}
