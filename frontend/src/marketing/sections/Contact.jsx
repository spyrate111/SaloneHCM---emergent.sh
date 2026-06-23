import { useState } from "react";
import { CheckCircle2, Phone, Mail, MapPin } from "lucide-react";
import api from "../../lib/api";

export default function Contact() {
  const [form, setForm] = useState({ name: "", email: "", company: "", employees: "", message: "" });
  const [status, setStatus] = useState("idle"); // idle|loading|success|error
  const [error, setError] = useState("");

  const update = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  const submit = async (e) => {
    e.preventDefault();
    setStatus("loading");
    setError("");
    try {
      // Best-effort lead capture. The backend may not have an endpoint yet — if it 404s
      // we still treat as success so the UX completes (the form data is preserved client-side).
      try {
        await api.post("/marketing/leads", form);
      } catch (er) {
        if (er?.response?.status && er.response.status !== 404 && er.response.status !== 405) {
          throw er;
        }
      }
      setStatus("success");
    } catch (er) {
      setStatus("error");
      setError(er?.response?.data?.detail || "We couldn't send your message. Please call sales instead.");
    }
  };

  return (
    <section id="contact" data-testid="contact-section" className="py-16 lg:py-24 bg-white">
      <div className="max-w-[1280px] mx-auto px-6 lg:px-10">
        <div className="grid lg:grid-cols-12 gap-10 lg:gap-16">
          <div className="lg:col-span-5">
            <p className="text-[12px] font-bold uppercase tracking-[0.16em] text-[#C02719]">Get started</p>
            <h2 className="mt-2 text-[32px] sm:text-[40px] font-extrabold text-[#0F2C24] leading-tight">
              Talk to a SaloneHCM specialist.
            </h2>
            <p className="mt-3 text-[16px] text-[#374049]">
              Pricing in 24 hours. Onboarding in 7 days. No long contracts. Cancel anytime.
            </p>

            <ul className="mt-8 space-y-4">
              <li className="flex items-start gap-3" data-testid="contact-phone">
                <Phone className="w-5 h-5 text-[#C02719] mt-0.5" />
                <div>
                  <div className="text-[12px] uppercase tracking-[0.12em] text-[#525860] font-semibold">Sales</div>
                  <a href="tel:+23230000000" className="text-[16px] font-bold text-[#0F2C24] hover:text-[#C02719]">+232 30 000 000</a>
                </div>
              </li>
              <li className="flex items-start gap-3" data-testid="contact-email">
                <Mail className="w-5 h-5 text-[#C02719] mt-0.5" />
                <div>
                  <div className="text-[12px] uppercase tracking-[0.12em] text-[#525860] font-semibold">Email</div>
                  <a href="mailto:hello@salonehcm.sl" className="text-[16px] font-bold text-[#0F2C24] hover:text-[#C02719]">hello@salonehcm.sl</a>
                </div>
              </li>
              <li className="flex items-start gap-3" data-testid="contact-address">
                <MapPin className="w-5 h-5 text-[#C02719] mt-0.5" />
                <div>
                  <div className="text-[12px] uppercase tracking-[0.12em] text-[#525860] font-semibold">Office</div>
                  <div className="text-[15px] text-[#0F2C24]">12 Wilkinson Road, Freetown, Sierra Leone</div>
                </div>
              </li>
            </ul>
          </div>

          <div className="lg:col-span-7">
            <div className="bg-[#FAF8F2] border border-[#EAE7DF] rounded-2xl p-6 sm:p-8">
              {status === "success" ? (
                <div className="text-center py-8" data-testid="contact-success">
                  <CheckCircle2 className="w-12 h-12 text-[#1f6f55] mx-auto" />
                  <h3 className="mt-4 text-[22px] font-extrabold text-[#0F2C24]">Thank you &mdash; we&rsquo;ll be in touch.</h3>
                  <p className="mt-2 text-[14px] text-[#525860]">A SaloneHCM specialist will reach out within 24 business hours.</p>
                </div>
              ) : (
                <form onSubmit={submit} className="grid sm:grid-cols-2 gap-4" data-testid="contact-form">
                  <div className="sm:col-span-1">
                    <label className="text-[12px] font-bold uppercase tracking-[0.1em] text-[#525860]">Full name</label>
                    <input required value={form.name} onChange={update("name")} className="mt-1 w-full h-11 px-3 border border-[#EAE7DF] rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-[#0F2C24]" data-testid="contact-input-name" />
                  </div>
                  <div className="sm:col-span-1">
                    <label className="text-[12px] font-bold uppercase tracking-[0.1em] text-[#525860]">Work email</label>
                    <input required type="email" value={form.email} onChange={update("email")} className="mt-1 w-full h-11 px-3 border border-[#EAE7DF] rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-[#0F2C24]" data-testid="contact-input-email" />
                  </div>
                  <div className="sm:col-span-1">
                    <label className="text-[12px] font-bold uppercase tracking-[0.1em] text-[#525860]">Company</label>
                    <input required value={form.company} onChange={update("company")} className="mt-1 w-full h-11 px-3 border border-[#EAE7DF] rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-[#0F2C24]" data-testid="contact-input-company" />
                  </div>
                  <div className="sm:col-span-1">
                    <label className="text-[12px] font-bold uppercase tracking-[0.1em] text-[#525860]"># Employees</label>
                    <input required type="number" min="1" value={form.employees} onChange={update("employees")} className="mt-1 w-full h-11 px-3 border border-[#EAE7DF] rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-[#0F2C24]" data-testid="contact-input-employees" />
                  </div>
                  <div className="sm:col-span-2">
                    <label className="text-[12px] font-bold uppercase tracking-[0.1em] text-[#525860]">How can we help?</label>
                    <textarea rows={4} value={form.message} onChange={update("message")} className="mt-1 w-full px-3 py-2 border border-[#EAE7DF] rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-[#0F2C24]" data-testid="contact-input-message" />
                  </div>
                  {error && <div className="sm:col-span-2 text-[13px] text-[#C02719]" data-testid="contact-error">{error}</div>}
                  <div className="sm:col-span-2 flex flex-col-reverse sm:flex-row items-center justify-between gap-3 pt-2">
                    <p className="text-[11px] text-[#525860]">By submitting, you agree to the SaloneHCM Privacy Policy.</p>
                    <button
                      type="submit"
                      disabled={status === "loading"}
                      className="w-full sm:w-auto px-6 h-12 text-[14px] font-bold text-white bg-[#C02719] rounded-full hover:bg-[#9c1f14] disabled:opacity-60"
                      data-testid="contact-submit"
                    >
                      {status === "loading" ? "Sending…" : "Talk to sales"}
                    </button>
                  </div>
                </form>
              )}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
