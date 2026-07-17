import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Play, Clock, ArrowUpRight } from "lucide-react";
import api from "../../lib/api";
import VideoPlayer from "../VideoPlayer";

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

const CATEGORY_LABELS = {
  getting_started: "Getting started",
  by_persona: "By industry",
  deep_dive: "Deep dive",
};

export default function VideoLibrary() {
  const [videos, setVideos] = useState([]);
  const [featured, setFeatured] = useState(null);
  const [activeId, setActiveId] = useState(null);

  useEffect(() => {
    api.get("/marketing/videos?limit=12").then((r) => {
      const list = r.data || [];
      setVideos(list);
      if (list.length > 0) {
        setFeatured(list[0]);
        setActiveId(list[0].id);
      }
    }).catch(() => {});
  }, []);

  if (videos.length === 0) {
    return null; // gracefully omit section if library is empty
  }

  const onPick = (v) => {
    setFeatured(v);
    setActiveId(v.id);
    // Smooth-scroll to the player so the user sees the change
    document.getElementById("video-featured-player")?.scrollIntoView({ behavior: "smooth", block: "center" });
  };

  return (
    <section
      id="videos"
      data-testid="video-library-section"
      className="py-16 lg:py-24 bg-white"
    >
      <div className="max-w-[1280px] mx-auto px-6 lg:px-10">
        <div className="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-4 mb-10">
          <div className="max-w-[680px]">
            <p className="text-[12px] font-bold uppercase tracking-[0.16em] text-[#0072C6]">See it in action</p>
            <h2 className="mt-2 text-[32px] sm:text-[40px] font-extrabold text-[#073A16] leading-tight">
              Watch how Sierra Leone employers use SaloneHCM.
            </h2>
            <p className="mt-3 text-[15px] text-[#374049]">
              Short product walkthroughs by use case &mdash; from a small Freetown business running its first payroll to a ministry filing PAYE for 5,000+ employees.
            </p>
          </div>
          <Link to="/videos" className="inline-flex items-center gap-1.5 text-[14px] font-bold text-[#073A16] hover:text-[#0072C6]" data-testid="video-library-see-all">
            Browse the full library <ArrowUpRight className="w-4 h-4" />
          </Link>
        </div>

        <div className="grid lg:grid-cols-12 gap-6 lg:gap-8">
          {/* Featured player */}
          <div className="lg:col-span-8" id="video-featured-player">
            {featured && <VideoPlayer video={featured} />}
            {featured && (
              <div className="mt-4">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-[10px] font-bold uppercase tracking-[0.14em] bg-[#073A16] text-white px-2 py-0.5 rounded-full">
                    {CATEGORY_LABELS[featured.category] || featured.category}
                  </span>
                  <span className="text-[10px] font-bold uppercase tracking-[0.14em] bg-[#E5F1FD] text-[#0072C6] px-2 py-0.5 rounded-full">
                    {PERSONA_LABELS[featured.persona] || featured.persona}
                  </span>
                  <span className="text-[11px] text-[#525860] flex items-center gap-1"><Clock className="w-3 h-3" /> {fmt(featured.duration_s)}</span>
                </div>
                <h3 className="mt-3 text-[20px] font-extrabold text-[#073A16]">{featured.title}</h3>
                <p className="mt-1.5 text-[14px] text-[#525860] leading-relaxed">{featured.summary}</p>
              </div>
            )}
          </div>

          {/* Playlist */}
          <aside className="lg:col-span-4">
            <p className="text-[11px] font-bold uppercase tracking-[0.14em] text-[#525860] mb-3">Up next ({videos.length})</p>
            <ul className="space-y-2 max-h-[560px] overflow-y-auto pr-1" data-testid="video-playlist">
              {videos.map((v) => (
                <li key={v.id}>
                  <button
                    type="button"
                    onClick={() => onPick(v)}
                    className={`w-full text-left flex gap-3 p-2.5 rounded-lg transition-colors ${activeId === v.id ? "bg-[#E5F1FD] ring-2 ring-[#0072C6]/15" : "bg-white hover:bg-[#FAF8F2]"}`}
                    data-testid={`video-playlist-item-${v.id}`}
                  >
                    <div className="relative w-[120px] aspect-video bg-[#073A16] rounded-md overflow-hidden flex-none">
                      {v.poster ? (
                        <img src={v.poster} alt="" className="absolute inset-0 w-full h-full object-cover" loading="lazy" />
                      ) : null}
                      <span className="absolute inset-0 grid place-items-center bg-black/30">
                        <Play className="w-5 h-5 text-white" fill="white" />
                      </span>
                      <span className="absolute bottom-1 right-1 px-1 text-[9px] font-mono bg-black/70 text-white rounded">
                        {fmt(v.duration_s)}
                      </span>
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className={`text-[12.5px] font-bold leading-snug line-clamp-2 ${activeId === v.id ? "text-[#0072C6]" : "text-[#073A16]"}`}>{v.title}</div>
                      <div className="text-[10.5px] text-[#525860] mt-0.5">{PERSONA_LABELS[v.persona] || v.persona}</div>
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          </aside>
        </div>
      </div>
    </section>
  );
}

function fmt(s) {
  if (!s) return "0:00";
  const t = Math.floor(s);
  const m = Math.floor(t / 60);
  const r = t % 60;
  return `${m}:${String(r).padStart(2, "0")}`;
}
