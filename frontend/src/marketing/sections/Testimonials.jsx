import { Quote, Star } from "lucide-react";

const TESTIMONIALS = [
  {
    quote: "We replaced three spreadsheets and a payroll consultant with SaloneHCM. Our last NRA PAYE return was filed in 9 minutes — and it was right.",
    name: "Aminata Kamara",
    role: "Director of Finance, Freetown Logistics Ltd.",
    rating: 5,
  },
  {
    quote: "The Civil Service module saved us. Ghost-worker audits used to take a quarter — now they take a morning. Auditor-General loves the report PDF.",
    name: "Mohamed Sesay",
    role: "Permanent Secretary, Ministry of Works",
    rating: 5,
  },
  {
    quote: "Field allowances for our project staff used to be a nightmare. The NGO sector preset bundle is exactly the four allowances we needed.",
    name: "Fatmata Bangura",
    role: "Country Director, AID Sierra Leone",
    rating: 5,
  },
];

const AWARDS = [
  { title: "Best HR-Tech Sierra Leone 2025", source: "WIA Awards" },
  { title: "GovTech Innovation of the Year", source: "Africa Public Sector Tech" },
  { title: "Top 50 African SaaS to watch", source: "TechCabal" },
  { title: "Certified by NRA", source: "Sierra Leone National Revenue Authority" },
];

export default function Testimonials() {
  return (
    <>
      <section
        id="testimonials"
        data-testid="testimonials-section"
        className="py-16 lg:py-24 bg-white"
      >
        <div className="max-w-[1280px] mx-auto px-6 lg:px-10">
          <div className="max-w-[760px] mb-12">
            <p className="text-[12px] font-bold uppercase tracking-[0.16em] text-[#0072C6]">Customer stories</p>
            <h2 className="mt-2 text-[32px] sm:text-[40px] font-extrabold text-[#073A16] leading-tight">
              Real results, from real Sierra Leone employers.
            </h2>
          </div>
          <div className="grid lg:grid-cols-3 gap-5">
            {TESTIMONIALS.map((t) => (
              <figure
                key={t.name}
                className="bg-[#FAF8F2] border border-[#EAE7DF] rounded-2xl p-7 flex flex-col"
                data-testid={`testimonial-${t.name.split(" ")[0].toLowerCase()}`}
              >
                <Quote className="w-6 h-6 text-[#0072C6] mb-3" />
                <blockquote className="text-[15px] text-[#073A16] leading-relaxed flex-1">{t.quote}</blockquote>
                <div className="mt-5 flex items-center gap-1">
                  {Array.from({ length: t.rating }).map((_, i) => (
                    <Star key={`${t.name}-star-${i}`} className="w-4 h-4 text-[#E07B4A] fill-[#E07B4A]" />
                  ))}
                </div>
                <figcaption className="mt-3 leading-tight">
                  <div className="font-bold text-[14px] text-[#073A16]">{t.name}</div>
                  <div className="text-[12px] text-[#525860]">{t.role}</div>
                </figcaption>
              </figure>
            ))}
          </div>
        </div>
      </section>

      <section
        id="awards"
        data-testid="awards-section"
        className="py-12 bg-[#FAF8F2] border-y border-[#EAE7DF]"
      >
        <div className="max-w-[1280px] mx-auto px-6 lg:px-10">
          <h2 className="text-center text-[14px] font-bold uppercase tracking-[0.16em] text-[#073A16] mb-7">
            Awards & recognition
          </h2>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            {AWARDS.map((a) => (
              <div
                key={a.title}
                className="bg-white border border-[#EAE7DF] rounded-xl p-5 text-center hover:border-[#073A16] transition-colors"
                data-testid={`award-${a.title.split(" ")[0].toLowerCase()}`}
              >
                <div className="w-12 h-12 mx-auto rounded-full bg-[#FAF8F2] grid place-items-center text-[#E07B4A] font-bold text-[18px]">
                  ★
                </div>
                <div className="mt-3 text-[13px] font-extrabold text-[#073A16] leading-snug">{a.title}</div>
                <div className="mt-1 text-[11px] text-[#525860]">{a.source}</div>
              </div>
            ))}
          </div>
        </div>
      </section>
    </>
  );
}
