import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

function pad(n) { return String(n).padStart(2, "0"); }

export default function PromoBanner() {
  // Countdown to end of current month, midnight Freetown
  const [diff, setDiff] = useState({ d: 0, h: 0, m: 0, s: 0 });
  const nav = useNavigate();

  useEffect(() => {
    const tick = () => {
      const now = new Date();
      const end = new Date(now.getFullYear(), now.getMonth() + 1, 1, 0, 0, 0); // first of next month
      let ms = end.getTime() - now.getTime();
      if (ms < 0) ms = 0;
      const d = Math.floor(ms / 86_400_000);
      ms -= d * 86_400_000;
      const h = Math.floor(ms / 3_600_000);
      ms -= h * 3_600_000;
      const m = Math.floor(ms / 60_000);
      ms -= m * 60_000;
      const s = Math.floor(ms / 1_000);
      setDiff({ d, h, m, s });
    };
    tick();
    const t = setInterval(tick, 1000);
    return () => clearInterval(t);
  }, []);

  return (
    <div data-testid="promo-banner" className="bg-[#0072C6] text-white">
      <div className="max-w-[1280px] mx-auto px-4 lg:px-10 py-2.5 flex flex-col sm:flex-row items-center justify-center gap-3 sm:gap-6 text-center">
        <div className="flex items-center gap-2 text-[12px] sm:text-[13px]">
          <span className="hidden sm:inline-block uppercase tracking-[0.14em] font-bold text-white/85">Limited offer ends in</span>
          <div className="flex items-center gap-1 font-mono font-bold text-[15px]" data-testid="promo-countdown">
            <span className="bg-white/15 rounded px-1.5 py-0.5">{pad(diff.d)}<span className="text-[10px] ml-0.5 font-normal">d</span></span>
            <span className="text-white/60">:</span>
            <span className="bg-white/15 rounded px-1.5 py-0.5">{pad(diff.h)}<span className="text-[10px] ml-0.5 font-normal">h</span></span>
            <span className="text-white/60">:</span>
            <span className="bg-white/15 rounded px-1.5 py-0.5">{pad(diff.m)}<span className="text-[10px] ml-0.5 font-normal">m</span></span>
            <span className="text-white/60">:</span>
            <span className="bg-white/15 rounded px-1.5 py-0.5">{pad(diff.s)}<span className="text-[10px] ml-0.5 font-normal">s</span></span>
          </div>
        </div>
        <p className="text-[13px] sm:text-[14px]">
          New customers: get up to <span className="font-bold">3 months free</span> on every paid plan.{" "}
          <a href="#contact" className="underline underline-offset-2 hover:no-underline">See terms</a>
        </p>
        <button
          type="button"
          onClick={() => nav("/pricing")}
          className="px-4 h-8 text-[12.5px] font-bold bg-white text-[#0072C6] rounded-full hover:bg-[#FAF8F2] transition-colors"
          data-testid="promo-cta"
        >
          Claim offer
        </button>
      </div>
    </div>
  );
}
