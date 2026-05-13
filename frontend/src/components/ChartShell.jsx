/* Measures parent then renders Recharts charts with explicit pixel dimensions,
   sidestepping the Recharts width(-1) / height(-1) warning that fires when
   ResponsiveContainer is mounted before its parent has a measurable width. */
import { useEffect, useRef, useState, cloneElement, isValidElement, Children } from "react";

export default function ChartShell({ height = 256, children, className = "" }) {
  const ref = useRef(null);
  const [size, setSize] = useState({ w: 0, h: 0 });

  useEffect(() => {
    if (!ref.current) return;
    const measure = () => {
      const r = ref.current?.getBoundingClientRect();
      if (r && r.width > 1) setSize({ w: Math.floor(r.width), h: Math.floor(r.height || height) });
    };
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(ref.current);
    return () => ro.disconnect();
  }, [height]);

  // Pass explicit width/height props to the (single) ResponsiveContainer child
  // so it never measures itself when parent is still 0×0.
  let measured = null;
  if (size.w > 0) {
    const kid = Children.only(children);
    measured = isValidElement(kid)
      ? cloneElement(kid, { width: size.w, height: size.h || height })
      : kid;
  }

  return (
    <div ref={ref} className={className} style={{ width: "100%", height, minWidth: 0 }}>
      {measured}
    </div>
  );
}
