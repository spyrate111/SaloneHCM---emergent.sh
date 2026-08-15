/**
 * Mobile training center — the same AI-narrated walkthrough videos as the
 * marketing site, in all 4 languages (English, Krio, Mende, Temne), sized
 * for field staff on phones. List cached in localStorage for offline browse.
 */
import { useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import api from "../../lib/api";
import { GraduationCap, Clock, Play, CheckCircle2, Users, ChevronDown, ChevronUp } from "lucide-react";

const CACHE_KEY = "salonehcm_m_training";
const LANG_KEY = "salonehcm_m_training_lang";
const LANGS = [
  { id: "en", label: "English" },
  { id: "krio", label: "Krio" },
  { id: "mende", label: "Mɛnde" },
  { id: "temne", label: "Temne" },
];

export default function MobileTraining() {
  const [videos, setVideos] = useState(() => {
    try { return JSON.parse(localStorage.getItem(CACHE_KEY) || "[]"); } catch { return []; }
  });
  const [lang, setLang] = useState(() => localStorage.getItem(LANG_KEY) || "en");
  const [active, setActive] = useState(null);
  const videoRef = useRef(null);
  const [done, setDone] = useState(new Set());
  const [total, setTotal] = useState(0);
  const [team, setTeam] = useState(null); // null = not supervisor/admin

  useEffect(() => {
    api.get("/training-progress/me")
      .then((r) => { setDone(new Set(r.data.completed || [])); setTotal(r.data.total || 0); })
      .catch(() => {});
    api.get("/training-progress/team").then((r) => setTeam(r.data)).catch(() => setTeam(null));
  }, []);

  const markComplete = async () => {
    if (!active?.base_slug || done.has(active.base_slug)) return;
    try {
      await api.post("/training-progress/complete", { base_slug: active.base_slug, lang: active.lang || "en" });
      setDone((s) => new Set([...s, active.base_slug]));
      toast.success("Video completed ✓");
    } catch { /* offline — will re-mark next watch */ }
  };

  useEffect(() => {
    api.get("/marketing/videos", { params: { category: "training", limit: 60 } })
      .then((r) => {
        const list = r.data || [];
        setVideos(list);
        try { localStorage.setItem(CACHE_KEY, JSON.stringify(list)); } catch { /* quota */ }
      })
      .catch(() => { /* keep cache */ });
  }, []);

  // group by base_slug → pick the variant for the chosen language (fallback en)
  const list = useMemo(() => {
    const bySlug = {};
    videos.forEach((v) => {
      const key = v.base_slug || v.slug || v.id;
      bySlug[key] = bySlug[key] || {};
      bySlug[key][v.lang || "en"] = v;
    });
    return Object.values(bySlug)
      .map((set) => set[lang] || set.en)
      .filter(Boolean)
      .sort((a, b) => (a.sort || 0) - (b.sort || 0));
  }, [videos, lang]);

  // keep the active video in sync when the language changes
  useEffect(() => {
    if (!active) return;
    const swap = list.find((v) => v.base_slug === active.base_slug);
    if (swap && swap.id !== active.id) setActive(swap);
  }, [list]); // eslint-disable-line react-hooks/exhaustive-deps

  const pickLang = (id) => {
    setLang(id);
    localStorage.setItem(LANG_KEY, id);
    api.post("/training-progress/lang", { lang: id }).catch(() => {}); // weekly reminders use it
  };

  return (
    <div className="p-4 space-y-4" data-testid="mobile-training">
      <div>
        <h1 className="text-lg font-bold text-[#0A4A1E] flex items-center gap-2">
          <GraduationCap className="w-5 h-5" /> Training center
        </h1>
        <p className="text-[11px] text-[#525860] mt-1">
          Short walkthroughs in your language — payslips, leave, clocking & more.
        </p>
        {total > 0 && (
          <div className="flex items-center gap-2 mt-2" data-testid="mobile-training-my-progress">
            <div className="flex-1 h-1.5 rounded-full bg-[#EBE8E0] overflow-hidden">
              <div className={`h-full rounded-full ${done.size >= total ? "bg-[#17A035]" : "bg-[#0A4A1E]"}`}
                   style={{ width: `${Math.round((done.size / total) * 100)}%` }} />
            </div>
            <span className="text-[10px] font-data text-[#525860]">{done.size}/{total} done</span>
          </div>
        )}
      </div>

      {/* language toggle */}
      <div className="flex rounded-full border border-[#E2DFD6] bg-white overflow-hidden" data-testid="mobile-training-lang-toggle">
        {LANGS.map((l) => (
          <button
            key={l.id}
            onClick={() => pickLang(l.id)}
            className={`flex-1 py-2 text-[11px] font-bold uppercase tracking-wide transition-colors ${
              lang === l.id ? "bg-[#0A4A1E] text-white" : "text-[#0A4A1E]"
            }`}
            data-testid={`mobile-training-lang-${l.id}`}
          >
            {l.label}
          </button>
        ))}
      </div>

      {/* active player */}
      {active && (
        <div className="space-y-2" data-testid="mobile-training-player">
          <div className="relative w-full aspect-video bg-black rounded-xl overflow-hidden">
            <video
              ref={videoRef}
              key={active.id}
              src={active.src}
              poster={active.poster || undefined}
              controls
              playsInline
              autoPlay
              onEnded={markComplete}
              className="absolute inset-0 w-full h-full"
              data-testid="mobile-training-video"
            >
              {(active.captions || []).map((c) => (
                <track key={c.src} kind="subtitles" src={c.src} srcLang={c.srclang} label={c.label} default />
              ))}
            </video>
          </div>
          <div>
            <div className="text-sm font-bold text-[#1A1C1E]">{active.title}</div>
            <div className="text-[11px] text-[#525860] mt-0.5 line-clamp-2">{active.summary}</div>
          </div>
        </div>
      )}

      {/* playlist */}
      <section className="space-y-2" data-testid="mobile-training-list">
        <div className="text-[10px] uppercase tracking-widest text-[#525860]">
          {list.length} video{list.length === 1 ? "" : "s"} · {LANGS.find((l) => l.id === lang)?.label}
        </div>
        {list.length === 0 && (
          <div className="text-center py-10 text-[#525860]" data-testid="mobile-training-empty">
            <GraduationCap className="w-10 h-10 mx-auto text-[#A1A5AB]" />
            <p className="mt-2 text-xs">No training videos available yet.</p>
          </div>
        )}
        {list.map((v) => (
          <button
            key={v.id}
            onClick={() => { setActive(v); window.scrollTo({ top: 0, behavior: "smooth" }); }}
            className={`w-full text-left flex gap-3 p-2.5 rounded-xl border transition-colors ${
              active?.id === v.id ? "bg-[#E4F7E7] border-[#B7E6C0]" : "bg-white border-[#E2DFD6] active:bg-[#F7F6F2]"
            }`}
            data-testid={`mobile-training-item-${v.base_slug || v.id}`}
          >
            <div className="relative w-[110px] aspect-video bg-[#073A16] rounded-lg overflow-hidden flex-none">
              {v.poster && <img src={v.poster} alt="" className="absolute inset-0 w-full h-full object-cover" loading="lazy" />}
              <span className="absolute inset-0 grid place-items-center bg-black/25">
                <Play className="w-5 h-5 text-white" fill="white" />
              </span>
            </div>
            <div className="flex-1 min-w-0">
              <div className={`text-[12px] font-bold leading-snug line-clamp-2 ${active?.id === v.id ? "text-[#0A4A1E]" : "text-[#1A1C1E]"}`}>
                {v.title}
              </div>
              <div className="text-[10px] text-[#525860] mt-1 flex items-center gap-1">
                <Clock className="w-3 h-3" /> {fmt(v.duration_s)}
                {done.has(v.base_slug) && (
                  <span className="inline-flex items-center gap-0.5 text-[#17A035] font-bold ml-1"
                        data-testid={`mobile-training-done-${v.base_slug}`}>
                    <CheckCircle2 className="w-3 h-3" /> Completed
                  </span>
                )}
              </div>
            </div>
          </button>
        ))}
      </section>

      {/* team progress — supervisors & admins only */}
      {team && <TeamProgress team={team} />}
    </div>
  );
}

function TeamProgress({ team }) {
  const [open, setOpen] = useState(null); // expanded employee_id
  const rows = team.rows.filter((r) => r.has_account);
  return (
    <section className="bg-white border border-[#E2DFD6] rounded-xl p-3 space-y-2" data-testid="mobile-training-team">
      <div className="flex items-center gap-2">
        <Users className="w-4 h-4 text-[#0A4A1E]" />
        <div className="flex-1">
          <div className="text-sm font-semibold text-[#0A4A1E]">Team progress</div>
          <div className="text-[10px] text-[#525860]">{rows.length} staff · {team.total} videos</div>
        </div>
      </div>
      <div className="divide-y divide-[#F1EEE6]">
        {rows.map((r) => {
          const doneSet = new Set(r.completed);
          const pct = team.total ? Math.round((r.completed_count / team.total) * 100) : 0;
          const expanded = open === r.employee_id;
          return (
            <div key={r.employee_id} className="py-2" data-testid={`mobile-training-team-row-${r.employee_id}`}>
              <button className="w-full flex items-center gap-2"
                      onClick={() => setOpen(expanded ? null : r.employee_id)}>
                <div className="flex-1 min-w-0 text-left">
                  <div className="text-xs font-semibold truncate">{r.name}</div>
                  <div className="text-[10px] text-[#8A8F96] truncate">{r.branch_name || "—"}</div>
                </div>
                <div className="w-20 h-1.5 rounded-full bg-[#EBE8E0] overflow-hidden">
                  <div className={`h-full rounded-full ${pct === 100 ? "bg-[#17A035]" : "bg-[#0A4A1E]"}`} style={{ width: `${pct}%` }} />
                </div>
                <span className="text-[10px] font-data text-[#525860] w-8 text-right">{r.completed_count}/{team.total}</span>
                {expanded ? <ChevronUp className="w-3.5 h-3.5 text-[#8A8F96]" /> : <ChevronDown className="w-3.5 h-3.5 text-[#8A8F96]" />}
              </button>
              {expanded && (
                <div className="mt-2 space-y-1 pl-1" data-testid={`mobile-training-team-detail-${r.employee_id}`}>
                  {team.videos.map((v) => (
                    <div key={v.base_slug} className="flex items-center gap-1.5 text-[10px]">
                      {doneSet.has(v.base_slug)
                        ? <CheckCircle2 className="w-3 h-3 text-[#17A035] flex-shrink-0" />
                        : <span className="w-3 h-3 rounded-full border border-[#D9D6CC] flex-shrink-0" />}
                      <span className={doneSet.has(v.base_slug) ? "text-[#1A1C1E]" : "text-[#8A8F96]"}>{v.title}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
        {!rows.length && <div className="py-4 text-center text-[11px] text-[#8A8F96]">No staff with accounts in your scope.</div>}
      </div>
    </section>
  );
}

function fmt(s) {
  if (!s) return "0:00";
  const t = Math.floor(s);
  return `${Math.floor(t / 60)}:${String(t % 60).padStart(2, "0")}`;
}

