import { useEffect, useMemo, useState } from "react";
import { Clock, Play, Search, Filter } from "lucide-react";
import MarketingLayout from "./MarketingLayout";
import VideoPlayer from "./VideoPlayer";
import api from "../lib/api";

const CATEGORIES = [
  { id: "all",             label: "All videos" },
  { id: "getting_started", label: "Getting started" },
  { id: "by_persona",      label: "By industry" },
  { id: "deep_dive",       label: "Deep dives" },
];

const PERSONA_LABELS = {
  small_business: "Small business",
  midsize: "Midsize",
  enterprise: "Enterprise",
  government: "Government & MDAs",
  ngo: "NGO",
  mining: "Mining",
  banking: "Banking",
  general: "All clients",
};

export default function VideosPage() {
  const [videos, setVideos] = useState([]);
  const [active, setActive] = useState(null);
  const [cat, setCat] = useState("all");
  const [q, setQ] = useState("");

  useEffect(() => {
    api.get("/marketing/videos?limit=60").then((r) => {
      const list = r.data || [];
      setVideos(list);
      if (list.length > 0) setActive(list[0]);
    }).catch(() => {});
  }, []);

  const visible = useMemo(() => {
    const term = q.trim().toLowerCase();
    return videos.filter((v) => {
      if (cat !== "all" && v.category !== cat) return false;
      if (term && !`${v.title} ${v.summary}`.toLowerCase().includes(term)) return false;
      return true;
    });
  }, [videos, cat, q]);

  return (
    <MarketingLayout>
      <section className="bg-gradient-to-b from-[#FAF8F2] to-white py-12 lg:py-16" data-testid="videos-page">
        <div className="max-w-[1280px] mx-auto px-6 lg:px-10">
          <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-[#C02719]">Training library</p>
          <h1 className="mt-2 text-[40px] sm:text-[48px] font-extrabold text-[#0F2C24] leading-[1.05]">
            SaloneHCM, <span className="text-[#C02719]">on demand</span>.
          </h1>
          <p className="mt-3 text-[16px] text-[#374049] max-w-[680px]">
            Short, focused walkthroughs by client type and use case. Pick what your team needs &mdash; or watch them all back-to-back.
          </p>
        </div>
      </section>

      <section className="py-8 lg:py-12">
        <div className="max-w-[1280px] mx-auto px-6 lg:px-10">
          <div className="grid lg:grid-cols-12 gap-6 lg:gap-8">
            {/* Featured */}
            <div className="lg:col-span-8">
              {active && <VideoPlayer video={active} />}
              {active && (
                <div className="mt-4">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-[10px] font-bold uppercase tracking-[0.14em] bg-[#0F2C24] text-white px-2 py-0.5 rounded-full">
                      {CATEGORIES.find((c) => c.id === active.category)?.label || active.category}
                    </span>
                    <span className="text-[10px] font-bold uppercase tracking-[0.14em] bg-[#FFE9E5] text-[#C02719] px-2 py-0.5 rounded-full">
                      {PERSONA_LABELS[active.persona] || active.persona}
                    </span>
                    <span className="text-[11px] text-[#525860] flex items-center gap-1"><Clock className="w-3 h-3" /> {fmt(active.duration_s)}</span>
                  </div>
                  <h2 className="mt-3 text-[24px] font-extrabold text-[#0F2C24]">{active.title}</h2>
                  <p className="mt-2 text-[14px] text-[#525860] leading-relaxed">{active.summary}</p>
                </div>
              )}
            </div>

            {/* Sidebar: filters + playlist */}
            <aside className="lg:col-span-4 space-y-4">
              <div className="bg-[#FAF8F2] border border-[#EAE7DF] rounded-xl p-4">
                <div className="flex items-center gap-2">
                  <Filter className="w-3.5 h-3.5 text-[#525860]" />
                  <span className="text-[11px] font-bold uppercase tracking-[0.14em] text-[#525860]">Filter</span>
                </div>
                <div className="mt-3 flex flex-wrap gap-1.5" data-testid="videos-category-filter">
                  {CATEGORIES.map((c) => {
                    const isActive = cat === c.id;
                    return (
                      <button
                        key={c.id}
                        type="button"
                        onClick={() => setCat(c.id)}
                        className={`px-2.5 h-7 text-[11px] font-semibold rounded-full transition-colors ${isActive ? "bg-[#C02719] text-white" : "bg-white text-[#0F2C24] hover:bg-[#F1EEE6]"}`}
                        data-testid={`videos-category-${c.id}`}
                      >
                        {c.label}
                      </button>
                    );
                  })}
                </div>
                <div className="mt-3 relative">
                  <Search className="w-3.5 h-3.5 text-[#9aa0a6] absolute left-2.5 top-1/2 -translate-y-1/2" />
                  <input
                    type="search"
                    value={q}
                    onChange={(e) => setQ(e.target.value)}
                    placeholder="Search videos…"
                    className="w-full pl-8 pr-3 h-9 text-[12.5px] bg-white border border-[#EAE7DF] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#0F2C24]"
                    data-testid="videos-search-input"
                  />
                </div>
              </div>

              <div>
                <p className="text-[11px] font-bold uppercase tracking-[0.14em] text-[#525860] mb-2">{visible.length} video{visible.length === 1 ? "" : "s"}</p>
                <ul className="space-y-2 max-h-[560px] overflow-y-auto pr-1" data-testid="videos-list">
                  {visible.map((v) => (
                    <li key={v.id}>
                      <button
                        type="button"
                        onClick={() => setActive(v)}
                        className={`w-full text-left flex gap-3 p-2.5 rounded-lg transition-colors ${active?.id === v.id ? "bg-[#FFE9E5] ring-2 ring-[#C02719]/15" : "bg-white hover:bg-[#FAF8F2]"}`}
                        data-testid={`videos-item-${v.id}`}
                      >
                        <div className="relative w-[120px] aspect-video bg-[#0F2C24] rounded-md overflow-hidden flex-none">
                          {v.poster ? <img src={v.poster} alt="" className="absolute inset-0 w-full h-full object-cover" loading="lazy" /> : null}
                          <span className="absolute inset-0 grid place-items-center bg-black/30">
                            <Play className="w-5 h-5 text-white" fill="white" />
                          </span>
                          <span className="absolute bottom-1 right-1 px-1 text-[9px] font-mono bg-black/70 text-white rounded">{fmt(v.duration_s)}</span>
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className={`text-[12.5px] font-bold leading-snug line-clamp-2 ${active?.id === v.id ? "text-[#C02719]" : "text-[#0F2C24]"}`}>{v.title}</div>
                          <div className="text-[10.5px] text-[#525860] mt-0.5">{PERSONA_LABELS[v.persona] || v.persona}</div>
                        </div>
                      </button>
                    </li>
                  ))}
                  {visible.length === 0 && (
                    <li className="text-center py-8 text-[12px] text-[#525860]">No videos match your filters.</li>
                  )}
                </ul>
              </div>
            </aside>
          </div>
        </div>
      </section>
    </MarketingLayout>
  );
}

function fmt(s) {
  if (!s) return "0:00";
  const t = Math.floor(s);
  const m = Math.floor(t / 60);
  const r = t % 60;
  return `${m}:${String(r).padStart(2, "0")}`;
}
