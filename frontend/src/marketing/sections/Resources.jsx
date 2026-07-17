import { Link } from "react-router-dom";
import { ArrowUpRight, BookOpen, FileText, Newspaper } from "lucide-react";

const RESOURCES = [
  {
    badge: "Guide",
    icon: BookOpen,
    title: "The Sierra Leone Payroll Compliance Checklist",
    desc: "Everything an SL employer must file each month — PAYE, NASSIT, GST, withholding tax.",
    accent: "bg-[#E5F1FD] text-[#0072C6]",
  },
  {
    badge: "Insights",
    icon: Newspaper,
    title: "Beyond the spreadsheet: HR data that actually drives decisions",
    desc: "How leading SL employers use dashboards to retain top talent and control payroll spend.",
    accent: "bg-[#E2F5E5] text-[#128A2C]",
  },
  {
    badge: "White paper",
    icon: FileText,
    title: "Civil service modernization: a blueprint for IFMIS-ready payroll",
    desc: "Best practice from MDAs that have moved off manual ledgers onto auditable systems.",
    accent: "bg-[#FFF1E3] text-[#E07B4A]",
  },
];

export default function Resources() {
  return (
    <section
      id="resources"
      data-testid="resources-section"
      className="py-16 lg:py-24 bg-[#FAF8F2]"
    >
      <div className="max-w-[1280px] mx-auto px-6 lg:px-10">
        <div className="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-4 mb-10">
          <div className="max-w-[680px]">
            <p className="text-[12px] font-bold uppercase tracking-[0.16em] text-[#0072C6]">Insights & resources</p>
            <h2 className="mt-2 text-[32px] sm:text-[40px] font-extrabold text-[#073A16] leading-tight">
              Practical guides for Sierra Leone employers.
            </h2>
          </div>
          <a href="#" className="inline-flex items-center gap-1.5 text-[14px] font-bold text-[#073A16] hover:text-[#0072C6]" data-testid="resources-see-all">
            Browse all insights <ArrowUpRight className="w-4 h-4" />
          </a>
        </div>

        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {RESOURCES.map((r) => {
            const Icon = r.icon;
            return (
              <article
                key={r.title}
                className="bg-white border border-[#EAE7DF] rounded-xl overflow-hidden hover:shadow-lg transition-all group"
                data-testid={`resource-${r.badge.toLowerCase().replace(/\s+/g, "-")}`}
              >
                <div className={`h-40 ${r.accent} grid place-items-center relative overflow-hidden`}>
                  <Icon className="w-12 h-12" />
                  <div className="absolute inset-0 bg-gradient-to-br from-white/0 to-white/20"></div>
                </div>
                <div className="p-5">
                  <span className={`inline-flex items-center px-2 h-5 text-[10px] font-bold uppercase tracking-[0.12em] rounded ${r.accent}`}>{r.badge}</span>
                  <h3 className="mt-3 text-[16px] font-extrabold text-[#073A16] leading-snug group-hover:text-[#0072C6] transition-colors">{r.title}</h3>
                  <p className="mt-2 text-[13px] text-[#525860] leading-relaxed">{r.desc}</p>
                  <a href="#" className="mt-3 inline-flex items-center gap-1 text-[12.5px] font-bold text-[#0072C6] hover:gap-2 transition-all">
                    Read article <ArrowUpRight className="w-3.5 h-3.5" />
                  </a>
                </div>
              </article>
            );
          })}
        </div>
      </div>
    </section>
  );
}
