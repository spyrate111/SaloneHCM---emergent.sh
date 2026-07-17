import { useEffect, useMemo, useRef, useState } from "react";
import { Play, Pause, Volume2, VolumeX, Maximize2, Loader2 } from "lucide-react";

/** Universal video player.
 *  Detects YouTube / Vimeo URLs and renders an iframe; otherwise uses a native
 *  <video> with poster, custom play button, mute toggle and a chapters list. */
export default function VideoPlayer({ video, autoPlay = false, className = "" }) {
  const kind = useMemo(() => detectKind(video?.src), [video?.src]);
  if (!video) return null;

  if (kind === "youtube" || kind === "vimeo") {
    return (
      <div className={`relative w-full aspect-video bg-black rounded-2xl overflow-hidden ${className}`} data-testid="video-player">
        <iframe
          src={embedUrl(video.src, kind, autoPlay)}
          title={video.title}
          allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
          allowFullScreen
          className="absolute inset-0 w-full h-full"
          data-testid="video-iframe"
        />
      </div>
    );
  }

  return <NativePlayer video={video} autoPlay={autoPlay} className={className} />;
}

function NativePlayer({ video, autoPlay, className }) {
  const ref = useRef(null);
  const [playing, setPlaying] = useState(false);
  const [muted, setMuted] = useState(true); // autoplay-friendly default
  const [loading, setLoading] = useState(true);
  const [t, setT] = useState(0);

  useEffect(() => {
    setLoading(true);
    setPlaying(false);
    setT(0);
  }, [video?.src]);

  useEffect(() => {
    const el = ref.current;
    if (!el || !autoPlay) return undefined;
    el.muted = true;
    el.play().catch(() => { /* browser may block — user has to click */ });
  }, [autoPlay, video?.src]);

  const toggle = () => {
    const el = ref.current;
    if (!el) return;
    if (el.paused) { el.play().catch(() => {}); } else { el.pause(); }
  };

  const goFullscreen = () => {
    const el = ref.current;
    if (!el) return;
    const req = el.requestFullscreen || el.webkitRequestFullscreen;
    if (req) req.call(el).catch(() => {});
  };

  const onTime = () => {
    const el = ref.current;
    if (el) setT(el.currentTime || 0);
  };

  const jump = (seconds) => {
    const el = ref.current;
    if (!el) return;
    el.currentTime = Math.max(0, Math.min(video.duration_s || el.duration || 0, seconds));
    el.play().catch(() => {});
  };

  const pct = video.duration_s ? Math.min(100, (t / video.duration_s) * 100) : 0;

  return (
    <div className={`relative w-full aspect-video bg-black rounded-2xl overflow-hidden group ${className}`} data-testid="video-player">
      <video
        ref={ref}
        src={video.src}
        poster={video.poster || undefined}
        playsInline
        preload="metadata"
        onPlay={() => setPlaying(true)}
        onPause={() => setPlaying(false)}
        onLoadedData={() => setLoading(false)}
        onTimeUpdate={onTime}
        onClick={toggle}
        className="absolute inset-0 w-full h-full cursor-pointer"
        data-testid="video-element"
      />

      {/* Big center play button when paused */}
      {!playing && (
        <button
          type="button"
          aria-label="Play video"
          onClick={toggle}
          className="absolute inset-0 grid place-items-center bg-black/30 hover:bg-black/40 transition-colors"
          data-testid="video-play-overlay"
        >
          {loading ? (
            <Loader2 className="w-12 h-12 text-white animate-spin" />
          ) : (
            <span className="w-20 h-20 rounded-full bg-white grid place-items-center shadow-xl group-hover:scale-105 transition-transform">
              <Play className="w-9 h-9 text-[#0072C6] ml-1.5" fill="#0072C6" />
            </span>
          )}
        </button>
      )}

      {/* Bottom controls */}
      <div className="absolute bottom-0 left-0 right-0 px-4 py-2.5 bg-gradient-to-t from-black/85 via-black/55 to-transparent opacity-0 group-hover:opacity-100 transition-opacity">
        <div className="h-1 rounded-full bg-white/20 overflow-hidden mb-2">
          <div className="h-full bg-[#E07B4A]" style={{ width: `${pct}%` }} />
        </div>
        <div className="flex items-center justify-between text-white">
          <div className="flex items-center gap-3">
            <button type="button" onClick={toggle} className="hover:text-[#E07B4A]" data-testid="video-play-toggle" aria-label={playing ? "Pause" : "Play"}>
              {playing ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
            </button>
            <button type="button" onClick={() => { if (ref.current) { ref.current.muted = !muted; setMuted(!muted); } }} className="hover:text-[#E07B4A]" data-testid="video-mute-toggle" aria-label={muted ? "Unmute" : "Mute"}>
              {muted ? <VolumeX className="w-4 h-4" /> : <Volume2 className="w-4 h-4" />}
            </button>
            <span className="text-[11px] font-mono">{fmt(t)} / {fmt(video.duration_s)}</span>
          </div>
          <button type="button" onClick={goFullscreen} className="hover:text-[#E07B4A]" aria-label="Fullscreen" data-testid="video-fullscreen">
            <Maximize2 className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Chapter markers */}
      {Array.isArray(video.chapters) && video.chapters.length > 0 && (
        <div className="absolute top-3 right-3 hidden lg:block max-w-[220px] space-y-1.5" data-testid="video-chapters">
          {video.chapters.map((c) => (
            <button
              key={c.t}
              type="button"
              onClick={() => jump(c.t)}
              className="block w-full text-left px-2.5 py-1.5 rounded-md text-[11px] bg-black/40 hover:bg-[#0072C6] text-white backdrop-blur-sm transition-colors"
            >
              <span className="font-mono text-[10px] opacity-80 mr-2">{fmt(c.t)}</span>
              {c.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function fmt(s) {
  if (!s && s !== 0) return "0:00";
  const t = Math.floor(s);
  const m = Math.floor(t / 60);
  const r = t % 60;
  return `${m}:${String(r).padStart(2, "0")}`;
}

function detectKind(src) {
  if (!src) return "unknown";
  if (/(?:youtu\.be|youtube\.com)/.test(src)) return "youtube";
  if (/vimeo\.com/.test(src)) return "vimeo";
  return "mp4";
}

function embedUrl(src, kind, autoPlay) {
  if (kind === "youtube") {
    const m = src.match(/(?:youtu\.be\/|youtube\.com\/watch\?v=)([\w-]{11})/);
    const id = m ? m[1] : "";
    const auto = autoPlay ? "1" : "0";
    return `https://www.youtube.com/embed/${id}?rel=0&modestbranding=1&autoplay=${auto}`;
  }
  if (kind === "vimeo") {
    const m = src.match(/vimeo\.com\/(\d+)/);
    const id = m ? m[1] : "";
    return `https://player.vimeo.com/video/${id}${autoPlay ? "?autoplay=1" : ""}`;
  }
  return src;
}
