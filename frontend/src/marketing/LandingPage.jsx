import MarketingLayout from "./MarketingLayout";
import Hero from "./sections/Hero";
import Personas from "./sections/Personas";
import ProductsGrid from "./sections/ProductsGrid";
import Industries from "./sections/Industries";
import StatsRow from "./sections/StatsRow";
import Resources from "./sections/Resources";
import Testimonials from "./sections/Testimonials";
import VideoLibrary from "./sections/VideoLibrary";
import Contact from "./sections/Contact";

export default function LandingPage() {
  return (
    <MarketingLayout>
      <Hero />
      <Personas />
      <ProductsGrid />
      <VideoLibrary />
      <Industries />
      <StatsRow />
      <Resources />
      <Testimonials />
      <Contact />
    </MarketingLayout>
  );
}
