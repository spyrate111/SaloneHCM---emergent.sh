/**
 * Desktop month-grid leave calendar — managers/admins only (the backend
 * 403s everyone else, which hides the section entirely).
 */
import { useEffect, useMemo, useState } from "react";
import api from "../lib/api";
import { ChevronLeft, ChevronRight, CalendarDays } from "lucide-react";
import { ymNow, shiftMonth, daysInMonth, firstDow, monthLabel, buildDayMap, todayKey } from "../lib/leaveCal";

const DOW = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

export default function LeaveCalendar() {
  const [month, setMonth] = useState(ymNow());
  const [data, setData] = useState(null);

  useEffect(() => {
    api.get("/leave/calendar", { params: { month } })
      .then((r) => setData(r.data))
      .catch(() => setData(null));
  }, [month]);

  const dayMap = useMemo(() => (data ? buildDayMap(month, data.leaves) : {}), [data, month]);
  if (!data) return null;

  const n = daysInMonth(month);
  const pad = firstDow(month);
  const cells = [...Array(pad).fill(null), ...Array.from({ length: n }, (_, i) => i + 1)];
  const tKey = todayKey();

  return (
    <div className="bg-white border border-[#E2DFD6] rounded-lg overflow-hidden" data-testid="leave-calendar">
      <div className="px-6 py-4 border-b border-[#E2DFD6] flex items-center gap-3 flex-wrap">
        <h3 className="font-heading text-lg font-semibold flex items-center gap-2">
          <CalendarDays className="w-4 h-4 text-[#0A4A1E]" /> Team leave calendar
        </h3>
        <div className="flex items-center gap-2 text-[11px]">
          <span className="inline-flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-sm bg-[#17A035]"></span> approved</span>
          <span className="inline-flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-sm bg-[#D8A31A]"></span> pending</span>
        </div>
        <div className="ml-auto flex items-center gap-1">
          <button onClick={() => setMonth(shiftMonth(month, -1))}
            className="p-1.5 rounded-md border border-[#E2DFD6] hover:bg-[#F7F6F2]"
            data-testid="leave-calendar-prev" aria-label="Previous month">
            <ChevronLeft className="w-4 h-4" />
          </button>
          <div className="text-sm font-semibold w-40 text-center" data-testid="leave-calendar-month">{monthLabel(month)}</div>
          <button onClick={() => setMonth(shiftMonth(month, 1))}
            className="p-1.5 rounded-md border border-[#E2DFD6] hover:bg-[#F7F6F2]"
            data-testid="leave-calendar-next" aria-label="Next month">
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      </div>
      <div className="grid grid-cols-7 border-b border-[#E2DFD6] bg-[#F7F6F2]">
        {DOW.map((d) => (
          <div key={d} className="py-2 text-center text-[10px] uppercase tracking-wider text-[#525860] font-medium">{d}</div>
        ))}
      </div>
      <div className="grid grid-cols-7">
        {cells.map((day, i) => {
          if (day === null) return <div key={`pad-${i}`} className="min-h-[92px] border-b border-r border-[#F1EEE6] bg-[#FBFAF7]" />;
          const key = `${month}-${String(day).padStart(2, "0")}`;
          const lvs = dayMap[key] || [];
          const isToday = key === tKey;
          return (
            <div key={key} className={`min-h-[92px] border-b border-r border-[#F1EEE6] p-1.5 ${isToday ? "bg-[#E4F7E7]/50" : ""}`}
                 data-testid={`leave-calendar-day-${key}`}>
              <div className={`text-[11px] font-data mb-1 ${isToday ? "font-bold text-[#0A4A1E]" : "text-[#525860]"}`}>{day}</div>
              <div className="space-y-0.5">
                {lvs.slice(0, 3).map((lv) => (
                  <div key={`${lv.id}-${key}`} title={`${lv.employee_name} · ${lv.leave_type} · ${lv.status}`}
                       className={`text-[10px] leading-tight px-1.5 py-0.5 rounded truncate ${
                         lv.status === "approved" ? "bg-[#E4F7E7] text-[#0A4A1E]" : "bg-[#FBF1DE] text-[#8B6A14]"
                       }`}>
                    {lv.employee_name}
                  </div>
                ))}
                {lvs.length > 3 && (
                  <div className="text-[9px] text-[#686D76] px-1.5">+{lvs.length - 3} more</div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
