/**
 * Admin-only nudge analytics — weekly Monday reminder sends and the share of
 * recipients who finished a video within 7 days (backend 403s others → hidden).
 */
import { useEffect, useState } from "react";
import { toast } from "sonner";
import api from "../lib/api";
import { BellRing, Send } from "lucide-react";

export default function ReminderNudgeStats() {
  const [data, setData] = useState(null);
  const [sending, setSending] = useState(false);
  const [nudgeLang, setNudgeLang] = useState("all");
  const load = () =>
    api.get("/training-progress/reminders/stats")
      .then((r) => setData(r.data)).catch(() => setData(null));
  useEffect(() => { load(); }, []);
  if (!data) return null;
  const { weeks, totals, languages } = data;
  const LANG_LABEL = { en: "English", krio: "Krio", mende: "Mɛnde", temne: "Temne" };

  const sendNow = async () => {
    setSending(true);
    const langLabel = nudgeLang === "all"
      ? "each person's language"
      : ({ en: "English", krio: "Krio", mende: "Mɛnde", temne: "Temne" }[nudgeLang]);
    try {
      const payload = nudgeLang === "all" ? {} : { lang: nudgeLang };
      const { data: r } = await api.post("/training-progress/reminders/run-now", payload);
      if (r.skipped) {
        toast.info(`Nothing to send — ${r.skipped}`);
      } else if (r.reminded === 0) {
        toast.info(`No one to nudge — ${r.skipped_already} already reminded this week, ${r.skipped_complete} finished all videos`);
      } else {
        toast.success(`Sent ${r.reminded} reminder${r.reminded === 1 ? "" : "s"} in ${langLabel} (${r.delivered_to_devices} reached a device) · ${r.skipped_already} already nudged · ${r.skipped_complete} all done`);
      }
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not send reminders");
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="bg-white border border-[#E2DFD6] rounded-lg overflow-hidden" data-testid="reminder-nudge-stats">
      <div className="px-6 py-4 border-b border-[#E2DFD6] flex items-center gap-3 flex-wrap">
        <h3 className="font-heading text-lg font-semibold flex items-center gap-2">
          <BellRing className="w-4 h-4 text-[#0A4A1E]" /> Reminder nudge stats
        </h3>
        <span className="text-[11px] text-[#525860]">Monday push reminders · a video finished within 7 days counts as a win</span>
        <div className="ml-auto flex items-center gap-2">
          <select value={nudgeLang} onChange={(e) => setNudgeLang(e.target.value)}
            className="bg-white border border-[#E2DFD6] rounded-md px-2.5 py-2 text-xs"
            data-testid="nudge-lang-select">
            <option value="all">All languages</option>
            <option value="en">English</option>
            <option value="krio">Krio</option>
            <option value="mende">Mɛnde</option>
            <option value="temne">Temne</option>
          </select>
          <button onClick={sendNow} disabled={sending}
            className="inline-flex items-center gap-2 bg-[#0A4A1E] hover:bg-[#063514] text-white text-xs font-medium px-3 py-2 rounded-md disabled:opacity-50"
            data-testid="nudge-send-now-button">
            <Send className="w-3.5 h-3.5" /> {sending ? "Sending…" : "Send this week's nudges now"}
          </button>
        </div>
      </div>
      <div className="grid grid-cols-3 divide-x divide-[#E2DFD6] border-b border-[#E2DFD6] text-center">
        <div className="py-4" data-testid="nudge-stat-reminded">
          <div className="font-data text-2xl font-bold text-[#0A4A1E]">{totals.reminded}</div>
          <div className="text-[10px] uppercase tracking-wider text-[#525860] mt-0.5">Reminders sent</div>
        </div>
        <div className="py-4" data-testid="nudge-stat-delivered">
          <div className="font-data text-2xl font-bold text-[#26547C]">{totals.delivered}</div>
          <div className="text-[10px] uppercase tracking-wider text-[#525860] mt-0.5">Reached a device</div>
        </div>
        <div className="py-4" data-testid="nudge-stat-rate">
          <div className="font-data text-2xl font-bold text-[#8B6A14]">{totals.nudge_rate}%</div>
          <div className="text-[10px] uppercase tracking-wider text-[#525860] mt-0.5">Completed after nudge</div>
        </div>
      </div>
      {languages && (
        <div className="grid grid-cols-2 sm:grid-cols-4 divide-x divide-[#E2DFD6] border-b border-[#E2DFD6]" data-testid="nudge-lang-breakdown">
          {languages.map((l) => (
            <div key={l.lang} className="px-4 py-3" data-testid={`nudge-lang-${l.lang}`}>
              <div className="text-[10px] uppercase tracking-wider text-[#525860]">{LANG_LABEL[l.lang] || l.lang}</div>
              <div className="mt-1 flex items-baseline gap-2">
                <span className="font-data text-lg font-bold text-[#1A1C1E]">{l.reminded}</span>
                <span className="text-[10px] text-[#8A8F96]">sent</span>
                <span className={`ml-auto font-data text-xs font-bold ${l.reminded ? (l.nudge_rate >= 50 ? "text-[#17A035]" : "text-[#8B6A14]") : "text-[#A1A5AB]"}`}>
                  {l.reminded ? `${l.nudge_rate}%` : "—"}
                </span>
              </div>
              <div className="mt-1.5 h-1 rounded-full bg-[#F1EEE6] overflow-hidden">
                <div className={`h-full rounded-full ${l.nudge_rate >= 50 ? "bg-[#17A035]" : "bg-[#D8A31A]"}`}
                  style={{ width: `${Math.min(100, l.nudge_rate)}%` }} />
              </div>
            </div>
          ))}
        </div>
      )}
      {weeks.length === 0 ? (
        <div className="py-8 text-center text-sm text-[#686D76]" data-testid="nudge-stats-empty">
          No reminders sent yet — the first push goes out Monday 09:00 UTC.
        </div>
      ) : (
        <table className="w-full text-sm" data-testid="nudge-stats-table">
          <thead className="bg-[#F7F6F2]">
            <tr>
              {["Week", "Reminded", "Reached device", "Completed after", "Nudge rate"].map((h) => (
                <th key={h} className="text-left text-[10px] uppercase tracking-wider text-[#525860] py-3 px-4 font-medium">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {weeks.map((w) => (
              <tr key={w.week} className="border-t border-[#E2DFD6]" data-testid={`nudge-week-${w.week}`}>
                <td className="py-2.5 px-4 font-data font-semibold">{w.week}</td>
                <td className="py-2.5 px-4 font-data">{w.reminded}</td>
                <td className="py-2.5 px-4 font-data">{w.delivered}</td>
                <td className="py-2.5 px-4 font-data">{w.completed_after}</td>
                <td className="py-2.5 px-4 min-w-[160px]">
                  <div className="flex items-center gap-2">
                    <div className="flex-1 h-1.5 rounded-full bg-[#F1EEE6] overflow-hidden">
                      <div className={`h-full rounded-full ${w.nudge_rate >= 50 ? "bg-[#17A035]" : "bg-[#D8A31A]"}`}
                        style={{ width: `${Math.min(100, w.nudge_rate)}%` }} />
                    </div>
                    <span className="text-[11px] font-data text-[#525860] whitespace-nowrap">{w.nudge_rate}%</span>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
