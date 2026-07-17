import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import MarketingLayout from "./MarketingLayout";
import api from "../lib/api";
import {
  GraduationCap, BookOpen, HelpCircle, Download, Award, PlayCircle,
  FileText, CheckCircle2, XCircle, ChevronDown,
} from "lucide-react";

const BACKEND = process.env.REACT_APP_BACKEND_URL;

const TABS = [
  { id: "articles", label: "Knowledge base", icon: BookOpen },
  { id: "faq", label: "FAQ", icon: HelpCircle },
  { id: "quizzes", label: "Quizzes & certification", icon: Award },
  { id: "downloads", label: "Downloads", icon: Download },
];

export default function TrainingCenterPage() {
  const [content, setContent] = useState(null);
  const [tab, setTab] = useState("articles");

  useEffect(() => {
    api.get("/public/training/content").then((r) => setContent(r.data)).catch(() => {});
  }, []);

  return (
    <MarketingLayout>
      <section className="bg-[#0A4A1E] text-white">
        <div className="max-w-6xl mx-auto px-6 py-16" data-testid="training-hero">
          <div className="text-[11px] uppercase tracking-[0.24em] text-[#D9C58A] font-semibold">SaloneHCM Academy</div>
          <h1 className="font-heading text-4xl sm:text-5xl font-bold mt-3 max-w-3xl">Training Center</h1>
          <p className="text-[#C9D4CE] mt-4 max-w-2xl text-base">
            Everything your team needs to master SaloneHCM — role-based video courses, knowledge base
            articles, quick reference cards, slide decks, and certification quizzes with downloadable certificates.
          </p>
          <Link to="/videos" data-testid="training-videos-link"
            className="inline-flex items-center gap-2 mt-6 bg-[#E07B4A] hover:bg-[#C9663A] text-white text-sm font-semibold px-5 py-3 rounded-md">
            <PlayCircle className="w-4 h-4" /> Watch the 7-video training series
          </Link>
        </div>
      </section>

      <section className="max-w-6xl mx-auto px-6 py-10" data-testid="training-page">
        <div className="flex flex-wrap gap-2 border-b border-[#E2DFD6] pb-3">
          {TABS.map((t) => (
            <button key={t.id} data-testid={`training-tab-${t.id}`} onClick={() => setTab(t.id)}
              className={`inline-flex items-center gap-1.5 text-sm px-4 py-2 rounded-md transition ${tab === t.id ? "bg-[#0A4A1E] text-white" : "text-[#525860] hover:bg-[#F7F6F2]"}`}>
              <t.icon className="w-4 h-4" /> {t.label}
            </button>
          ))}
        </div>
        <div className="mt-8">
          {!content ? (
            <p className="text-sm text-[#686D76]">Loading…</p>
          ) : tab === "articles" ? (
            <Articles articles={content.articles} />
          ) : tab === "faq" ? (
            <Faq faqs={content.faqs} />
          ) : tab === "quizzes" ? (
            <Quizzes quizzes={content.quizzes} />
          ) : (
            <Downloads resources={content.resources} />
          )}
        </div>
      </section>
    </MarketingLayout>
  );
}

function Articles({ articles }) {
  const [open, setOpen] = useState(null);
  const active = articles.find((a) => a.slug === open);
  if (active) {
    return (
      <div className="max-w-3xl" data-testid="article-view">
        <button onClick={() => setOpen(null)} className="text-sm text-[#26547C] hover:underline mb-4" data-testid="article-back">← All articles</button>
        <div className="text-[11px] uppercase tracking-wider text-[#8B6A14]">{active.role} · {active.minutes} min read</div>
        <h2 className="font-heading text-3xl font-bold mt-1">{active.title}</h2>
        <div className="mt-5 space-y-4">
          {active.body.map((p) =>
            p.startsWith("## ") ? (
              <h3 key={p} className="font-heading text-lg font-semibold text-[#0A4A1E] mt-6">{p.slice(3)}</h3>
            ) : (
              <p key={p} className="text-[15px] leading-relaxed text-[#33383F]">{p}</p>
            ))}
        </div>
      </div>
    );
  }
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4" data-testid="articles-grid">
      {articles.map((a) => (
        <button key={a.slug} data-testid={`article-card-${a.slug}`} onClick={() => setOpen(a.slug)}
          className="text-left bg-white border border-[#E2DFD6] rounded-lg p-5 hover:border-[#0A4A1E] hover:shadow-sm transition">
          <FileText className="w-5 h-5 text-[#26547C]" strokeWidth={1.6} />
          <h3 className="font-heading text-base font-semibold mt-3">{a.title}</h3>
          <div className="text-[11px] uppercase tracking-wider text-[#8B6A14] mt-2">{a.role} · {a.minutes} min</div>
        </button>
      ))}
    </div>
  );
}

function Faq({ faqs }) {
  const [open, setOpen] = useState(null);
  return (
    <div className="max-w-3xl divide-y divide-[#E2DFD6] border border-[#E2DFD6] rounded-lg bg-white" data-testid="faq-list">
      {faqs.map((f, i) => (
        <div key={f.q}>
          <button data-testid={`faq-q-${i}`} onClick={() => setOpen(open === i ? null : i)}
            className="w-full flex items-center justify-between text-left px-5 py-4 hover:bg-[#FDFCFB]">
            <span className="font-medium text-[15px] pr-4">{f.q}</span>
            <ChevronDown className={`w-4 h-4 text-[#686D76] shrink-0 transition-transform ${open === i ? "rotate-180" : ""}`} />
          </button>
          {open === i && <p className="px-5 pb-4 text-sm text-[#525860] leading-relaxed" data-testid={`faq-a-${i}`}>{f.a}</p>}
        </div>
      ))}
    </div>
  );
}

function Quizzes({ quizzes }) {
  const [active, setActive] = useState(null);
  if (active) return <QuizRunner quiz={active} onExit={() => setActive(null)} />;
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4" data-testid="quizzes-grid">
      {quizzes.map((q) => (
        <div key={q.id} className="bg-white border border-[#E2DFD6] rounded-lg p-5 flex flex-col" data-testid={`quiz-card-${q.id}`}>
          <Award className="w-5 h-5 text-[#8B6A14]" strokeWidth={1.6} />
          <h3 className="font-heading text-base font-semibold mt-3">{q.title}</h3>
          <div className="text-[11px] uppercase tracking-wider text-[#525860] mt-1.5">{q.role} · {q.questions.length} questions · pass {q.pass_pct}%</div>
          <p className="text-xs text-[#686D76] mt-2 flex-1">Pass to earn a personalised certificate PDF with a verification ID.</p>
          <button data-testid={`quiz-start-${q.id}`} onClick={() => setActive(q)}
            className="mt-4 bg-[#0A4A1E] hover:bg-[#063514] text-white text-sm px-4 py-2 rounded-md w-fit">Start quiz</button>
        </div>
      ))}
    </div>
  );
}

function QuizRunner({ quiz, onExit }) {
  const [answers, setAnswers] = useState(() => quiz.questions.map(() => null));
  const [name, setName] = useState("");
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const complete = useMemo(() => answers.every((a) => a !== null), [answers]);

  const submit = async () => {
    setBusy(true);
    try {
      const r = await api.post(`/public/training/quiz/${quiz.id}/submit`, { name: name.trim(), answers });
      setResult(r.data);
    } catch (e) {
      setResult({ error: e?.response?.data?.detail || "Submission failed" });
    } finally {
      setBusy(false);
    }
  };

  if (result && !result.error) {
    return (
      <div className="max-w-2xl" data-testid="quiz-result">
        <button onClick={onExit} className="text-sm text-[#26547C] hover:underline mb-4">← All quizzes</button>
        <div className={`rounded-lg border p-8 text-center ${result.passed ? "bg-[#E4F7E7] border-[#17A035]/40" : "bg-[#E9F2FB] border-[#3A7CB8]/40"}`}>
          {result.passed
            ? <CheckCircle2 className="w-10 h-10 text-[#17A035] mx-auto" />
            : <XCircle className="w-10 h-10 text-[#3A7CB8] mx-auto" />}
          <h3 className="font-heading text-2xl font-bold mt-3" data-testid="quiz-score">
            {result.score}% — {result.passed ? "Passed!" : "Not yet"}
          </h3>
          <p className="text-sm text-[#525860] mt-2">
            {result.correct} of {result.total} correct · pass mark {result.pass_pct}%
          </p>
          {result.passed && result.certificate_id && (
            <a data-testid="quiz-certificate-link"
              href={`${BACKEND}/api/public/training/certificates/${result.certificate_id}.pdf`}
              className="inline-flex items-center gap-2 mt-5 bg-[#0A4A1E] text-white text-sm px-5 py-2.5 rounded-md">
              <Download className="w-4 h-4" /> Download your certificate
            </a>
          )}
          {!result.passed && (
            <button onClick={() => { setResult(null); setAnswers(quiz.questions.map(() => null)); }}
              className="mt-5 border border-[#3A7CB8] text-[#3A7CB8] text-sm px-5 py-2.5 rounded-md" data-testid="quiz-retry">
              Try again
            </button>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-2xl" data-testid="quiz-runner">
      <button onClick={onExit} className="text-sm text-[#26547C] hover:underline mb-4" data-testid="quiz-exit">← All quizzes</button>
      <h2 className="font-heading text-2xl font-bold">{quiz.title}</h2>
      <p className="text-sm text-[#525860] mt-1">Answer all {quiz.questions.length} questions. Pass mark: {quiz.pass_pct}%.</p>
      {result?.error && <p className="text-sm text-[#3A7CB8] mt-2">{String(result.error)}</p>}
      <div className="space-y-6 mt-6">
        {quiz.questions.map((q, qi) => (
          <div key={q.q} className="bg-white border border-[#E2DFD6] rounded-lg p-5" data-testid={`quiz-question-${qi}`}>
            <p className="font-medium text-[15px]">{qi + 1}. {q.q}</p>
            <div className="mt-3 space-y-2">
              {q.options.map((opt, oi) => (
                <label key={opt} data-testid={`quiz-q${qi}-opt${oi}`}
                  className={`flex items-center gap-3 px-4 py-2.5 rounded-md border cursor-pointer text-sm transition ${answers[qi] === oi ? "border-[#0A4A1E] bg-[#EEF7EF]" : "border-[#E2DFD6] hover:bg-[#FDFCFB]"}`}>
                  <input type="radio" name={`q${qi}`} checked={answers[qi] === oi}
                    onChange={() => setAnswers((a) => a.map((v, i) => (i === qi ? oi : v)))}
                    className="accent-[#0A4A1E]" />
                  {opt}
                </label>
              ))}
            </div>
          </div>
        ))}
      </div>
      <div className="bg-white border border-[#E2DFD6] rounded-lg p-5 mt-6">
        <label className="block text-[11px] uppercase tracking-wider text-[#525860] mb-1">Your full name (appears on the certificate)</label>
        <input data-testid="quiz-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Fatmata Kamara"
          className="w-full bg-[#F7F6F2] border border-[#E2DFD6] rounded-md px-3 py-2 text-sm" />
        <button data-testid="quiz-submit" disabled={busy || !complete || name.trim().length < 2} onClick={submit}
          className="mt-4 bg-[#0A4A1E] hover:bg-[#063514] text-white text-sm px-6 py-2.5 rounded-md disabled:opacity-40">
          Submit answers
        </button>
        {!complete && <span className="ml-3 text-xs text-[#8B6A14]">Answer every question to submit.</span>}
      </div>
    </div>
  );
}

function Downloads({ resources }) {
  const groups = ["Reference card", "Checklist", "Scripts", "Presentation"];
  return (
    <div className="space-y-8" data-testid="downloads-list">
      {groups.map((g) => {
        const items = resources.filter((r) => r.kind === g);
        if (!items.length) return null;
        return (
          <div key={g}>
            <h3 className="text-[11px] uppercase tracking-[0.18em] text-[#525860] mb-3">{g.endsWith("s") ? g : `${g}s`}</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {items.map((r) => (
                <a key={r.file} data-testid={`download-${r.file}`} href={`${BACKEND}${r.url}`} download
                  className="bg-white border border-[#E2DFD6] rounded-lg p-5 hover:border-[#0A4A1E] hover:shadow-sm transition block">
                  <div className="flex items-center justify-between">
                    <GraduationCap className="w-5 h-5 text-[#17A035]" strokeWidth={1.6} />
                    <Download className="w-4 h-4 text-[#26547C]" />
                  </div>
                  <h4 className="font-heading text-sm font-semibold mt-3">{r.title}</h4>
                  <p className="text-xs text-[#686D76] mt-1.5">{r.desc}</p>
                  <span className="text-[10px] uppercase tracking-wider text-[#8B6A14] mt-2 inline-block">{r.file.split(".").pop()}</span>
                </a>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}
