import { useEffect } from "react";
import { useLocation } from "react-router-dom";
import PromoBanner from "./PromoBanner";
import MarketingNav from "./MarketingNav";
import MarketingFooter from "./MarketingFooter";

export default function MarketingLayout({ children }) {
  const loc = useLocation();

  // Scroll-to-anchor for #hash links coming in from menu items
  useEffect(() => {
    if (loc.hash) {
      const id = loc.hash.replace("#", "");
      const el = document.getElementById(id);
      if (el) {
        setTimeout(() => el.scrollIntoView({ behavior: "smooth", block: "start" }), 80);
      }
    } else {
      window.scrollTo({ top: 0, behavior: "instant" });
    }
  }, [loc.pathname, loc.hash]);

  return (
    <div className="min-h-screen bg-white text-[#0F2C24] font-sans">
      <PromoBanner />
      <MarketingNav />
      <main>{children}</main>
      <MarketingFooter />
    </div>
  );
}
