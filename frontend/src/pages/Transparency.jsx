import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import api from "../lib/api";
import { Landmark, ShieldCheck, Users, Wallet, Receipt, ArrowDownToLine, FileCheck, Globe } from "lucide-react";
import { LANGUAGES, t } from "../lib/i18nTransparency";

const fmtSLE = (v) => new Intl.NumberFormat("en", { style: "currency", currency: "SLE", maximumFractionDigits: 0 }).format(v);

export default function Transparency() {
  const { slug } = useParams();
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");
  const [lang, setLang] = useState(() => localStorage.getItem("salonehcm_lang") || "en");

  useEffect(() => {
    api.get(`/public/transparency/${slug}`)
      .then((r) => setData(r.data))
      .catch((e) => setErr(e?.response?.data?.detail || "Portal not found"));
  }, [slug]);

  useEffect(() => { localStorage.setItem("salonehcm_lang", lang); }, [lang]);

  if (err) {
    return (
      <div className="min-h-screen grid place-items-center bg-[#F7F6F2] p-6">
        <div className="text-center max-w-md">
          <Landmark className="w-12 h-12 mx-auto text-[#A1A5AB]" strokeWidth={1.3} />
          <h1 className="font-heading text-2xl font-bold mt-4">{t(lang, "portal_not_found")}</h1>
          <p className="text-sm text-[#525860] mt-2">{err}</p>
        </div>
      </div>
    );
  }
  if (!data) return null;
  const { organization, totals, ministries, last_payroll, compliance, as_of } = data;

  return (
    <div className="min-h-screen bg-[#F7F6F2]" data-testid="transparency-page">
      <header className="bg-gradient-to-br from-[#133326] via-[#0F281E] to-[#26547C] text-white relative overflow-hidden">
        <div className="absolute -top-20 -right-20 w-80 h-80 rounded-full bg-[#D1603D]/20 blur-3xl pointer-events-none" />
        <div className="max-w-6xl mx-auto px-6 sm:px-10 py-12 sm:py-16 relative">
          <div className="flex items-start justify-between gap-4 flex-wrap">
            <div>
              <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.22em] text-white/60">
                <ShieldCheck className="w-3.5 h-3.5" strokeWidth={1.7} /> {t(lang, "header_tag")}
              </div>
              <h1 className="font-heading text-3xl sm:text-5xl font-bold mt-3 leading-tight" data-testid="org-name">{organization.name}</h1>
            </div>
            <LanguagePicker lang={lang} setLang={setLang} />
          </div>
          <p className="text-white/75 mt-3 text-base sm:text-lg max-w-3xl leading-relaxed">{t(lang, "blurb")}</p>
          <div className="mt-5 flex items-center gap-3 text-xs text-white/70 font-data flex-wrap">
            <span>{t(lang, "as_of")} {new Date(as_of).toLocaleString()}</span>
            <span className="text-white/40">·</span>
            <span>{organization.country}</span>
            {organization.tier_label && (
              <>
                <span className="text-white/40">·</span>
                <span>{t(lang, "verified_by")} {organization.tier_label}</span>
              </>
            )}
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-6 sm:px-10 py-8 sm:py-12 space-y-8">
        <section data-testid="kpis" className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <KPI icon={Users} label={t(lang, "kpi_headcount")} value={totals.headcount.toLocaleString()} sub={t(lang, "kpi_headcount_sub", totals.ministries)} accent="bg-[#26547C]" />
          <KPI icon={Wallet} label={t(lang, "kpi_gross")} value={fmtSLE(totals.monthly_gross_sle)} sub={t(lang, "kpi_gross_sub")} accent="bg-[#133326]" />
          <KPI icon={Receipt} label={t(lang, "kpi_paye")} value={fmtSLE(totals.monthly_paye_sle)} sub={t(lang, "kpi_paye_sub")} accent="bg-[#D1603D]" />
          <KPI icon={ArrowDownToLine} label={t(lang, "kpi_nassit")} value={fmtSLE(totals.monthly_nassit_sle)} sub={t(lang, "kpi_nassit_sub")} accent="bg-[#2D7A5D]" />
        </section>

        <section className="bg-white border border-[#E2DFD6] rounded-xl overflow-hidden">
          <div className="px-6 py-4 border-b border-[#E2DFD6] flex items-center gap-2">
            <Landmark className="w-5 h-5 text-[#26547C]" strokeWidth={1.6} />
            <div>
              <h2 className="font-heading text-lg font-semibold">{t(lang, "by_ministry")}</h2>
              <p className="text-xs text-[#686D76] mt-0.5">{t(lang, "by_ministry_sub")}</p>
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm" data-testid="ministry-table">
              <thead className="bg-[#F7F6F2]">
                <tr>{[t(lang, "th_num"), t(lang, "th_ministry"), t(lang, "th_headcount"), t(lang, "th_gross"), t(lang, "th_paye"), t(lang, "th_nassit")].map((h, i) => (
                  <th key={i} className="text-left text-[10px] uppercase tracking-wider text-[#525860] py-3 px-4 font-medium">{h}</th>
                ))}</tr>
              </thead>
              <tbody>
                {ministries.map((m, i) => (
                  <tr key={m.name} className="border-t border-[#E2DFD6]">
                    <td className="py-3 px-4 font-data text-[#686D76]">{i + 1}</td>
                    <td className="py-3 px-4 font-medium">{m.name}</td>
                    <td className="py-3 px-4 font-data">{m.headcount}</td>
                    <td className="py-3 px-4 font-data font-semibold">{fmtSLE(m.monthly_gross_sle)}</td>
                    <td className="py-3 px-4 font-data text-[#B84F2F]">{fmtSLE(m.monthly_paye_sle)}</td>
                    <td className="py-3 px-4 font-data text-[#26547C]">{fmtSLE(m.monthly_nassit_sle)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="bg-white border border-[#E2DFD6] rounded-lg p-6" data-testid="last-payroll">
            <div className="text-[10px] uppercase tracking-wider text-[#525860] flex items-center gap-2">
              <Wallet className="w-3.5 h-3.5" /> {t(lang, "last_payroll")}
            </div>
            {last_payroll ? (
              <>
                <div className="font-heading text-2xl font-bold mt-2 font-data">{last_payroll.period}</div>
                <div className="text-xs text-[#686D76] mt-1">{t(lang, "ran_on")} {new Date(last_payroll.ran_at).toLocaleDateString()}</div>
              </>
            ) : (
              <div className="text-sm text-[#686D76] mt-2">{t(lang, "no_runs")}</div>
            )}
          </div>
          <div className="bg-white border border-[#E2DFD6] rounded-lg p-6" data-testid="compliance">
            <div className="text-[10px] uppercase tracking-wider text-[#525860] flex items-center gap-2">
              <FileCheck className="w-3.5 h-3.5" /> {t(lang, "filings_12m")}
            </div>
            <div className="font-heading text-2xl font-bold mt-2 font-data text-[#2D7A5D]">
              {compliance.returns_filed_12m}
              <span className="text-base text-[#A1A5AB] font-normal"> {t(lang, "returns_filed")}</span>
            </div>
            <div className="text-xs text-[#686D76] mt-1">
              {compliance.most_recent_filing ? `${t(lang, "most_recent_filing")} ${compliance.most_recent_filing}` : t(lang, "no_filings")}
            </div>
          </div>
        </section>

        <footer className="border-t border-[#E2DFD6] pt-6 text-xs text-[#686D76] text-center space-y-2">
          <div className="flex items-center justify-center gap-1.5">
            <ShieldCheck className="w-3.5 h-3.5 text-[#2D7A5D]" /> {t(lang, "footer_verified")}
          </div>
          <div>{t(lang, "footer_powered")} <span className="font-medium text-[#133326]">SaloneHCM</span> · {t(lang, "footer_ogp")}</div>
        </footer>
      </main>
    </div>
  );
}

function LanguagePicker({ lang, setLang }) {
  return (
    <div data-testid="language-picker" className="bg-white/10 border border-white/20 rounded-md px-3 py-1.5 inline-flex items-center gap-2 text-xs">
      <Globe className="w-3.5 h-3.5 text-white/70" strokeWidth={1.5} />
      {LANGUAGES.map((l) => (
        <button
          key={l.code}
          data-testid={`lang-${l.code}`}
          onClick={() => setLang(l.code)}
          className={`px-2 py-0.5 rounded transition ${lang === l.code ? "bg-white text-[#133326] font-semibold" : "text-white/80 hover:text-white"}`}
        >
          {l.label}
        </button>
      ))}
    </div>
  );
}

function KPI({ icon: Icon, label, value, sub, accent }) {
  return (
    <div className="bg-white border border-[#E2DFD6] rounded-lg p-4 flex items-start justify-between gap-3">
      <div className="min-w-0">
        <div className="text-[10px] uppercase tracking-[0.16em] text-[#525860]">{label}</div>
        <div className="font-heading text-xl sm:text-2xl font-bold mt-1 font-data">{value}</div>
        {sub && <div className="text-[10px] text-[#686D76] mt-0.5 truncate">{sub}</div>}
      </div>
      <div className={`w-9 h-9 rounded-md ${accent} grid place-items-center shrink-0`}>
        <Icon className="w-[18px] h-[18px] text-white" strokeWidth={1.5} />
      </div>
    </div>
  );
}
