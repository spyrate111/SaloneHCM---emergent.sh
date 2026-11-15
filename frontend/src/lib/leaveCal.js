// Month helpers shared by the desktop + mobile leave calendars.
export const ymNow = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
};

export const shiftMonth = (m, delta) => {
  const [y, mm] = m.split("-").map(Number);
  const d = new Date(y, mm - 1 + delta, 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
};

export const daysInMonth = (m) => {
  const [y, mm] = m.split("-").map(Number);
  return new Date(y, mm, 0).getDate();
};

// 0 = Sunday
export const firstDow = (m) => new Date(`${m}-01T00:00:00`).getDay();

export const monthLabel = (m) =>
  new Date(`${m}-01T00:00:00`).toLocaleDateString([], { month: "long", year: "numeric" });

// { "YYYY-MM-DD": [leave, ...] } for every day of `m` a leave overlaps.
export const buildDayMap = (m, leaves) => {
  const n = daysInMonth(m);
  const map = {};
  for (let d = 1; d <= n; d++) map[`${m}-${String(d).padStart(2, "0")}`] = [];
  (leaves || []).forEach((lv) => {
    for (let d = 1; d <= n; d++) {
      const key = `${m}-${String(d).padStart(2, "0")}`;
      if (lv.start_date <= key && key <= lv.end_date) map[key].push(lv);
    }
  });
  return map;
};

export const todayKey = () => new Date().toISOString().split("T")[0];
