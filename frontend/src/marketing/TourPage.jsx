import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  Play, Pause, Menu as MenuIcon, X, ChevronLeft, ChevronRight,
  Volume2, VolumeX, ArrowRight, CheckCircle2, Sparkles,
} from "lucide-react";
import { TOUR_MODULES } from "./tour/tourData";
import { OverviewMock, RunPayrollMock, HirePersonMock } from "./tour/MockScreens";

const MOCKS = {
  "overview":    OverviewMock,
  "run-payroll": RunPayrollMock,
  "hire-person": HirePersonMock,
};

const AUTOPLAY_MS = 5500;

export default function TourPage() {
  const nav = useNavigate();
  const [moduleIdx, setModuleIdx] = useState(0);
  const [stepIdx, setStepIdx] = useState(0);
  const [autoplay, setAutoplay] = useState(false);
  const [muted, setMuted] = useState(true); // sound is decorative; default muted
  const [menuOpen, setMenuOpen] = useState(false);
  const [showCongrats, setShowCongrats] = useState(false);
  const canvasRef = useRef(null);

  const current = TOUR_MODULES[moduleIdx];
  const Mock = MOCKS[current.id];
  const step = current.steps[stepIdx];
  const totalSteps = current.steps.length;
  const isLastStep = stepIdx >= totalSteps - 1;
  const isLastModule = moduleIdx >= TOUR_MODULES.length - 1;

  // Compute popup position pinned to the anchor element
  const [pos, setPos] = useState({ top: 100, left: 100, side: "right" });
  const recomputePos = useCallback(() => {
    if (!canvasRef.current) return;
    const canvas = canvasRef.current.getBoundingClientRect();
    const target = canvasRef.current.querySelector(`[data-tour-anchor="${step.anchor}"]`);
    if (!target) {
      setPos({ top: canvas.height / 2 - 60, left: canvas.width / 2 - 160, side: "center" });
      return;
    }
    const t = target.getBoundingClientRect();
    // Coordinates relative to canvas
    const cx = t.left - canvas.left;
    const cy = t.top - canvas.top;
    const popupW = 340, popupH = 200, gap = 14;
    let top = cy, left = cx;
    if (step.side === "right")  { left = cx + t.width + gap;       top = cy + t.height / 2 - popupH / 2; }
    if (step.side === "left")   { left = cx - popupW - gap;        top = cy + t.height / 2 - popupH / 2; }
    if (step.side === "top")    { left = cx + t.width / 2 - popupW / 2; top = cy - popupH - gap; }
    if (step.side === "bottom") { left = cx + t.width / 2 - popupW / 2; top = cy + t.height + gap; }
    // Clamp inside canvas
    top  = Math.max(12, Math.min(canvas.height - popupH - 12, top));
    left = Math.max(12, Math.min(canvas.width  - popupW - 12, left));
    setPos({ top, left, side: step.side || "right" });
  }, [step.anchor, step.side]);

  // Recompute when the step / module changes, and on resize
  useEffect(() => {
    const id = requestAnimationFrame(recomputePos);
    return () => cancelAnimationFrame(id);
  }, [recomputePos, moduleIdx, stepIdx]);

  useEffect(() => {
    const onR = () => recomputePos();
    window.addEventListener("resize", onR);
    return () => window.removeEventListener("resize", onR);
  }, [recomputePos]);

  // Autoplay timer
  const next = useCallback(() => {
    if (!isLastStep) {
      setStepIdx((s) => s + 1);
    } else {
      setShowCongrats(true);
      setAutoplay(false);
    }
  }, [isLastStep]);

  useEffect(() => {
    if (!autoplay || showCongrats || menuOpen) return undefined;
    const id = setTimeout(next, AUTOPLAY_MS);
    return () => clearTimeout(id);
  }, [autoplay, stepIdx, moduleIdx, showCongrats, menuOpen, next]);

  const back = () => setStepIdx((s) => Math.max(0, s - 1));

  const jumpToModule = (idx) => {
    setModuleIdx(idx);
    setStepIdx(0);
    setShowCongrats(false);
    setMenuOpen(false);
  };

  const continueTour = () => {
    if (isLastModule) {
      nav("/demo");
      return;
    }
    setModuleIdx((m) => m + 1);
    setStepIdx(0);
    setShowCongrats(false);
  };

  // Aggregate progress (across all modules)
  const overallProgress = useMemo(() => {
    const totals = TOUR_MODULES.reduce((acc, m) => acc + m.steps.length, 0);
    let done = 0;
    for (let i = 0; i < moduleIdx; i += 1) done += TOUR_MODULES[i].steps.length;
    done += stepIdx + (showCongrats ? 1 : 0);
    return { done, totals, pct: Math.min(100, Math.round((done / totals) * 100)) };
  }, [moduleIdx, stepIdx, showCongrats]);

  return (
    <div className="min-h-screen bg-[#073A16] flex flex-col" data-testid="tour-page">
      {/* Top toolbar — ADP-style */}
      <header className="flex items-center justify-between px-4 sm:px-6 lg:px-8 h-[60px] bg-[#073A16] text-white border-b border-white/10">
        <Link to="/" className="flex items-center gap-2.5 group" data-testid="tour-logo">
          <span className="w-9 h-9 rounded-md bg-white grid place-items-center text-[#073A16] font-bold tracking-tight">SH</span>
          <div className="leading-none">
            <div className="font-bold text-[14px]">SaloneHCM <span className="text-[#E07B4A]">Demo</span></div>
            <div className="text-[10px] text-white/60 uppercase tracking-[0.14em]">Interactive product tour</div>
          </div>
        </Link>

        <div className="flex items-center gap-2.5">
          <button
            type="button"
            onClick={() => setAutoplay((v) => !v)}
            className={`inline-flex items-center gap-1.5 px-4 h-9 text-[12px] font-bold rounded-full transition-colors ${autoplay ? "bg-[#E07B4A] text-white" : "bg-white text-[#073A16] hover:bg-[#FAF8F2]"}`}
            data-testid="tour-autoplay-toggle"
          >
            {autoplay ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />} {autoplay ? "Pause" : "Autoplay"}
          </button>
          <button
            type="button"
            onClick={() => setMenuOpen(true)}
            className="inline-flex items-center gap-1.5 px-4 h-9 text-[12px] font-bold border border-white text-white rounded-full hover:bg-white hover:text-[#073A16] transition-colors"
            data-testid="tour-menu-open"
          >
            <MenuIcon className="w-3.5 h-3.5" /> Demo menu
          </button>
          <button
            type="button"
            aria-label="Toggle sound"
            onClick={() => setMuted((v) => !v)}
            className="w-9 h-9 grid place-items-center border border-white/30 rounded-full hover:bg-white/10"
            data-testid="tour-sound-toggle"
          >
            {muted ? <VolumeX className="w-4 h-4" /> : <Volume2 className="w-4 h-4" />}
          </button>
        </div>
      </header>

      {/* Module title strip */}
      <div className="px-4 sm:px-6 lg:px-8 py-3 bg-[#073A16] text-white flex items-center justify-between gap-3 border-b border-white/10">
        <div>
          <div className="text-[10px] font-bold uppercase tracking-[0.14em] text-[#E07B4A]">Module {moduleIdx + 1} of {TOUR_MODULES.length}</div>
          <div className="text-[18px] font-extrabold" data-testid="tour-module-title">{current.title}: <span className="text-white/70 font-medium">{current.subtitle}</span></div>
        </div>
        <div className="hidden sm:block w-[260px]">
          <div className="text-[10px] text-white/60 mb-1 text-right" data-testid="tour-overall-progress">{overallProgress.pct}% complete</div>
          <div className="h-1.5 rounded-full bg-white/15 overflow-hidden">
            <div className="h-full bg-[#E07B4A] transition-all duration-500" style={{ width: `${overallProgress.pct}%` }} />
          </div>
        </div>
      </div>

      {/* Canvas — fake product screen + floating popup */}
      <main className="flex-1 p-4 sm:p-6 lg:p-8" data-testid="tour-canvas-wrapper">
        <div
          ref={canvasRef}
          className="relative bg-white rounded-2xl shadow-2xl overflow-hidden h-[600px] max-w-[1280px] mx-auto"
          data-testid="tour-canvas"
        >
          <Mock />

          {!showCongrats && (
            <TourPopup
              pos={pos}
              stepIdx={stepIdx}
              totalSteps={totalSteps}
              body={step.body}
              onBack={back}
              onNext={next}
              isFirst={stepIdx === 0}
              isLast={isLastStep}
            />
          )}

          {showCongrats && (
            <CongratsOverlay
              moduleTitle={current.title}
              isLastModule={isLastModule}
              onContinue={continueTour}
              onBookDemo={() => nav("/demo")}
            />
          )}
        </div>
      </main>

      {menuOpen && (
        <DemoMenu
          modules={TOUR_MODULES}
          currentIdx={moduleIdx}
          onClose={() => setMenuOpen(false)}
          onJump={jumpToModule}
        />
      )}
    </div>
  );
}

function TourPopup({ pos, stepIdx, totalSteps, body, onBack, onNext, isFirst, isLast }) {
  return (
    <div
      className="absolute bg-white rounded-xl shadow-2xl border border-[#EAE7DF] w-[340px] p-5 transition-all duration-300"
      style={{ top: pos.top, left: pos.left }}
      data-testid="tour-popup"
    >
      <div className="flex items-center justify-between">
        <span className="inline-flex items-center px-2 h-5 text-[9px] font-bold uppercase tracking-[0.14em] bg-[#073A16] text-white rounded-full">
          <Sparkles className="w-2.5 h-2.5 mr-1" /> Tour step
        </span>
        <span className="text-[10px] text-[#525860] font-mono" data-testid="tour-step-counter">{stepIdx + 1} OF {totalSteps}</span>
      </div>
      <p className="mt-3 text-[14px] text-[#073A16] leading-relaxed" data-testid="tour-popup-body">{body}</p>
      <div className="mt-4 flex items-center justify-between">
        <button
          type="button"
          onClick={onBack}
          disabled={isFirst}
          className="inline-flex items-center gap-1 text-[12px] font-semibold text-[#073A16] disabled:opacity-30"
          data-testid="tour-popup-back"
        >
          <ChevronLeft className="w-3.5 h-3.5" /> Back
        </button>
        <button
          type="button"
          onClick={onNext}
          className="inline-flex items-center gap-1 px-4 h-8 text-[12px] font-bold bg-[#0072C6] text-white rounded-full hover:bg-[#005A9C]"
          data-testid="tour-popup-next"
        >
          {isLast ? "Finish module" : "Next"} <ChevronRight className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  );
}

function CongratsOverlay({ moduleTitle, isLastModule, onContinue, onBookDemo }) {
  return (
    <div className="absolute inset-0 bg-white grid place-items-center p-8" data-testid="tour-congrats">
      <div className="max-w-[680px] text-center">
        <div className="w-20 h-20 rounded-full bg-[#E2F5E5] grid place-items-center mx-auto">
          <CheckCircle2 className="w-10 h-10 text-[#128A2C]" />
        </div>
        <p className="mt-5 text-[12px] font-bold uppercase tracking-[0.16em] text-[#0072C6]">{isLastModule ? "Tour complete" : "Module complete"}</p>
        <h2 className="mt-1.5 text-[28px] sm:text-[36px] font-extrabold text-[#073A16] leading-tight">
          {isLastModule
            ? <>You&rsquo;ve seen the full SaloneHCM picture.</>
            : <>Nicely done. <span className="text-[#0072C6]">{moduleTitle}</span> is in the bag.</>}
        </h2>
        <p className="mt-3 text-[15px] text-[#525860] max-w-[520px] mx-auto leading-relaxed">
          {isLastModule
            ? "Ready to see this run against your real employees, your real allowances, your real ministry? A specialist will set up a live sandbox in 24 hours."
            : "We&rsquo;ll keep going. Next up: a live walk-through of the next core flow."}
        </p>
        <div className="mt-7 flex items-center justify-center gap-3 flex-wrap">
          {isLastModule ? (
            <>
              <button
                type="button"
                onClick={onBookDemo}
                className="px-5 h-12 text-[14px] font-bold bg-[#0072C6] text-white rounded-full hover:bg-[#005A9C] inline-flex items-center gap-1.5"
                data-testid="tour-congrats-book"
              >
                Book my real demo <ArrowRight className="w-4 h-4" />
              </button>
              <Link to="/pricing" className="px-5 h-12 text-[14px] font-bold border border-[#073A16] text-[#073A16] rounded-full hover:bg-[#073A16] hover:text-white inline-flex items-center" data-testid="tour-congrats-pricing">
                See pricing
              </Link>
            </>
          ) : (
            <button
              type="button"
              onClick={onContinue}
              className="px-5 h-12 text-[14px] font-bold bg-[#0072C6] text-white rounded-full hover:bg-[#005A9C] inline-flex items-center gap-1.5"
              data-testid="tour-congrats-continue"
            >
              Continue the tour <ArrowRight className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function DemoMenu({ modules, currentIdx, onClose, onJump }) {
  return (
    <div className="fixed inset-0 z-50 bg-black/60 grid place-items-center p-4" onClick={onClose} data-testid="tour-menu-modal">
      <div
        className="bg-white rounded-2xl w-full max-w-[640px] p-6 sm:p-8 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between">
          <div>
            <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-[#0072C6]">Demo menu</p>
            <h3 className="text-[22px] font-extrabold text-[#073A16]">Pick a module to jump to.</h3>
          </div>
          <button type="button" onClick={onClose} aria-label="Close menu" className="w-9 h-9 grid place-items-center rounded-full border border-[#EAE7DF] hover:bg-[#FAF8F2]" data-testid="tour-menu-close">
            <X className="w-4 h-4" />
          </button>
        </div>
        <div className="mt-5 space-y-2">
          {modules.map((m, i) => {
            const active = i === currentIdx;
            return (
              <button
                key={m.id}
                type="button"
                onClick={() => onJump(i)}
                className={`w-full text-left p-4 rounded-xl border transition-all flex items-center gap-3 ${
                  active
                    ? "border-[#0072C6] bg-[#E5F1FD] ring-2 ring-[#0072C6]/15"
                    : "border-[#EAE7DF] bg-white hover:border-[#073A16]"
                }`}
                data-testid={`tour-menu-jump-${m.id}`}
              >
                <span className={`w-8 h-8 rounded-full grid place-items-center text-[12px] font-extrabold flex-none ${active ? "bg-[#0072C6] text-white" : "bg-[#FAF8F2] text-[#073A16]"}`}>{i + 1}</span>
                <div className="flex-1 min-w-0">
                  <div className={`text-[14px] font-extrabold ${active ? "text-[#0072C6]" : "text-[#073A16]"}`}>{m.title}</div>
                  <div className="text-[11.5px] text-[#525860] leading-snug">{m.subtitle} &middot; {m.steps.length} steps</div>
                </div>
                {active && <span className="text-[10px] font-bold uppercase tracking-[0.14em] bg-[#0072C6] text-white px-2 py-0.5 rounded-full">Active</span>}
              </button>
            );
          })}
        </div>
        <div className="mt-6 pt-4 border-t border-[#F1EEE6] text-center">
          <Link to="/demo" className="text-[12.5px] font-bold text-[#0072C6] hover:underline" onClick={onClose} data-testid="tour-menu-book-demo">
            Skip the tour &mdash; book a live demo instead &rarr;
          </Link>
        </div>
      </div>
    </div>
  );
}
