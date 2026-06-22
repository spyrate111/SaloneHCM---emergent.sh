import { useEffect, useState, useCallback } from "react";
import api, { fmtSLE } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { toast } from "sonner";
import {
  CreditCard, Building2, Check, Clock, X, Copy, Landmark, AlertTriangle, Receipt, ExternalLink,
} from "lucide-react";

const PLAN_ICON = {
  lite: "🌱",
  professional: "🚀",
  enterprise: "🏢",
  gov: "🏛",
};

export default function Billing() {
  const { user } = useAuth();
  const isAdmin = ["admin", "superadmin"].includes(user?.role);
  const [me, setMe] = useState(null);
  const [plans, setPlans] = useState([]);
  const [invoices, setInvoices] = useState([]);
  const [selectedPlan, setSelectedPlan] = useState(null);
  const [method, setMethod] = useState("bank_transfer");
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    const [mineRes, plansRes, invRes] = await Promise.all([
      api.get("/billing/me"),
      api.get("/billing/plans"),
      isAdmin ? api.get("/billing/invoices") : Promise.resolve({ data: [] }),
    ]);
    setMe(mineRes.data);
    setPlans(plansRes.data.plans);
    setInvoices(invRes.data);
  }, [isAdmin]);

  useEffect(() => { refresh(); }, [refresh]);

  // Handle return-from-Stripe (?session_id=…)
  useEffect(() => {
    const url = new URL(window.location.href);
    const sid = url.searchParams.get("session_id");
    if (!sid) return;
    api.get(`/billing/stripe/status/${sid}`).then((r) => {
      if (r.data.payment_status === "paid") {
        toast.success("Payment confirmed — your subscription is active!");
      } else if (r.data.payment_status === "expired") {
        toast.error("Stripe checkout expired. Please try again.");
      }
      // Clean the URL
      url.searchParams.delete("session_id");
      window.history.replaceState({}, "", url.toString());
      refresh();
    });
  }, [refresh]);

  if (!me) return <div className="text-sm text-[#525860] p-6">Loading billing…</div>;

  const issueBankInvoice = async () => {
    if (!selectedPlan) { toast.error("Pick a plan first"); return; }
    setBusy(true);
    try {
      await api.post("/billing/bank-transfer/invoice", { plan_id: selectedPlan });
      toast.success("Bank-transfer invoice created");
      setSelectedPlan(null);
      refresh();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Invoice creation failed");
    } finally { setBusy(false); }
  };

  const startStripe = async () => {
    if (!selectedPlan) { toast.error("Pick a plan first"); return; }
    setBusy(true);
    try {
      const { data } = await api.post("/billing/stripe/checkout", {
        plan_id: selectedPlan,
        origin_url: window.location.origin,
      });
      window.location.href = data.checkout_url;
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Stripe checkout failed");
    } finally { setBusy(false); }
  };

  return (
    <div className="space-y-6" data-testid="billing-page">
      <CurrentPlanCard me={me} />
      {me.open_invoice && <OpenInvoiceCard invoice={me.open_invoice} />}
      <PlansGrid plans={plans} currentPlanId={me.plan.id} selected={selectedPlan} onSelect={setSelectedPlan} />
      {selectedPlan && isAdmin && (
        <PaymentMethodCard
          plans={plans}
          selectedPlan={selectedPlan}
          method={method}
          setMethod={setMethod}
          busy={busy}
          onBank={issueBankInvoice}
          onStripe={startStripe}
        />
      )}
      {invoices.length > 0 && <InvoicesTable invoices={invoices} />}
    </div>
  );
}

function CurrentPlanCard({ me }) {
  const sub = me.subscription;
  const STATUS_PILL = {
    trialing: { bg: "bg-[#E5EEF6]", fg: "text-[#26547C]", label: "Trialing" },
    active: { bg: "bg-[#E6F4EC]", fg: "text-[#2D7A5D]", label: "Active" },
    past_due: { bg: "bg-[#FBF1DE]", fg: "text-[#8B6A14]", label: "Past due" },
    suspended: { bg: "bg-[#FBEAEA]", fg: "text-[#B83A3A]", label: "Suspended" },
  };
  const p = STATUS_PILL[sub.status] || STATUS_PILL.trialing;
  return (
    <div className="bg-white border border-[#E2DFD6] rounded-lg p-6" data-testid="billing-current">
      <div className="flex items-start justify-between flex-wrap gap-4">
        <div>
          <div className="text-[10px] uppercase tracking-[0.18em] text-[#525860]">Subscription</div>
          <h1 className="font-heading text-3xl font-bold mt-1">Billing</h1>
          <div className="flex items-center gap-3 mt-2">
            <span className="text-2xl">{PLAN_ICON[me.plan.id] || ""}</span>
            <div>
              <div className="text-lg font-semibold">{me.plan.label}</div>
              <span className={`inline-flex items-center text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-full ${p.bg} ${p.fg} mt-1`}>
                {p.label}
              </span>
            </div>
          </div>
        </div>
        <div className="text-right">
          <div className="text-[10px] uppercase tracking-wider text-[#525860]">Next payment</div>
          <div className="font-data font-semibold text-2xl">{fmtSLE(me.current_charge.total_sle)}</div>
          <div className="text-xs text-[#686D76] mt-0.5">
            {me.current_charge.extra_employees > 0
              ? `Includes ${me.current_charge.extra_employees} extra employees (SLE ${me.current_charge.extra_sle})`
              : `${me.employees} of ${me.plan.included_employees} employees included`}
          </div>
          {sub.current_period_end && (
            <div className="text-[10px] text-[#A1A5AB] mt-1">Period ends {new Date(sub.current_period_end).toLocaleDateString()}</div>
          )}
        </div>
      </div>
    </div>
  );
}

function OpenInvoiceCard({ invoice }) {
  const [copied, setCopied] = useState(null);
  const copy = (text, key) => {
    navigator.clipboard.writeText(text);
    setCopied(key);
    setTimeout(() => setCopied(null), 2000);
  };
  const bank = invoice.bank_details;
  return (
    <div className="bg-[#FBF8F2] border border-[#E8D5A2] rounded-lg p-6" data-testid="billing-open-invoice">
      <div className="flex items-start gap-3 mb-4">
        <Landmark className="w-6 h-6 text-[#8B6A14] flex-shrink-0 mt-0.5" strokeWidth={1.5} />
        <div className="flex-1">
          <div className="text-[10px] uppercase tracking-wider text-[#8B6A14] font-medium">Awaiting bank transfer</div>
          <h2 className="font-heading text-xl font-semibold mt-1">Pay {fmtSLE(invoice.total_sle)} by {new Date(invoice.due_date).toLocaleDateString()}</h2>
          <p className="text-xs text-[#525860] mt-1">Transfer the amount to the account below using <strong>this exact reference</strong>. Once received, our team will activate your subscription within 1 business day.</p>
        </div>
      </div>
      {bank && (
        <div className="bg-white border border-[#E2DFD6] rounded-md p-4 grid sm:grid-cols-2 gap-3 text-sm">
          <BankField label="Bank" value={bank.bank_name} />
          <BankField label="Account name" value={bank.account_name} />
          <BankField label="Account number" value={bank.account_number} copyable onCopy={() => copy(bank.account_number, "acct")} copied={copied === "acct"} />
          <BankField label="Branch / SWIFT" value={`${bank.branch_code} · ${bank.swift}`} />
          <BankField label="Currency" value={bank.currency} />
          <div className="sm:col-span-2 bg-[#E6F4EC] border border-[#C2E5D2] rounded-md p-3">
            <div className="text-[10px] uppercase tracking-wider text-[#2D7A5D] mb-1">Payment reference (REQUIRED)</div>
            <div className="flex items-center justify-between gap-2">
              <code className="font-data text-base font-bold text-[#1A3A2A]" data-testid="invoice-reference">{invoice.reference}</code>
              <button onClick={() => copy(invoice.reference, "ref")} className="text-xs inline-flex items-center gap-1 text-[#2D7A5D] hover:bg-[#D6EBE0] px-2 py-1 rounded">
                {copied === "ref" ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />} {copied === "ref" ? "Copied" : "Copy"}
              </button>
            </div>
            <div className="text-[10px] text-[#525860] mt-1.5">Without this reference, the payment cannot be matched to your account.</div>
          </div>
        </div>
      )}
    </div>
  );
}

function BankField({ label, value, copyable, onCopy, copied }) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-wider text-[#525860]">{label}</div>
      <div className="flex items-center gap-1.5">
        <div className="font-data text-sm font-medium">{value}</div>
        {copyable && (
          <button onClick={onCopy} className="text-[#26547C] hover:bg-[#F1EEE6] p-1 rounded">
            {copied ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
          </button>
        )}
      </div>
    </div>
  );
}

function PlansGrid({ plans, currentPlanId, selected, onSelect }) {
  return (
    <div className="bg-white border border-[#E2DFD6] rounded-lg p-6">
      <h2 className="font-heading text-xl font-semibold mb-4">Plans</h2>
      <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
        {plans.map((p) => {
          const isCurrent = p.id === currentPlanId;
          const isSelected = p.id === selected;
          return (
            <button
              key={p.id}
              data-testid={`plan-${p.id}`}
              onClick={() => !isCurrent && onSelect(p.id)}
              disabled={isCurrent}
              className={`text-left border rounded-md p-4 transition relative ${
                isCurrent ? "border-[#2D7A5D] bg-[#F1F8F4] cursor-default"
                : isSelected ? "border-[#26547C] bg-[#E5EEF6] ring-2 ring-[#26547C]"
                : "border-[#E2DFD6] hover:bg-[#F7F6F2]"
              }`}
            >
              <div className="text-2xl mb-1">{PLAN_ICON[p.id]}</div>
              <div className="font-heading text-lg font-semibold">{p.label}</div>
              <div className="font-data text-2xl font-bold mt-1">{fmtSLE(p.monthly_sle)}<span className="text-xs text-[#686D76]">/mo</span></div>
              <p className="text-xs text-[#525860] mt-2">{p.description}</p>
              <p className="text-[10px] text-[#686D76] mt-2">{p.included_employees} employees included · SLE {p.extra_employee_sle} per extra</p>
              {isCurrent && (
                <span className="absolute top-3 right-3 text-[9px] uppercase tracking-widest font-semibold bg-[#2D7A5D] text-white px-1.5 py-0.5 rounded-full">Current</span>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function PaymentMethodCard({ plans, selectedPlan, method, setMethod, busy, onBank, onStripe }) {
  const plan = plans.find((p) => p.id === selectedPlan);
  if (!plan) return null;
  return (
    <div className="bg-white border border-[#E2DFD6] rounded-lg p-6" data-testid="billing-payment-method">
      <h2 className="font-heading text-xl font-semibold mb-1">Pay for {plan.label}</h2>
      <p className="text-xs text-[#525860] mb-4">Choose how to settle your monthly invoice.</p>
      <div className="grid sm:grid-cols-2 gap-3">
        <PaymentOption
          active={method === "bank_transfer"}
          onClick={() => setMethod("bank_transfer")}
          icon={Landmark}
          label="Bank transfer"
          subtitle="SLCB · Rokel · Ecobank · GTBank · UBA"
          badge="Recommended in Sierra Leone"
          testid="method-bank"
        />
        <PaymentOption
          active={method === "stripe"}
          onClick={() => setMethod("stripe")}
          icon={CreditCard}
          label="Card / Stripe"
          subtitle="Visa, Mastercard, Apple Pay (USD)"
          badge="International"
          testid="method-stripe"
        />
      </div>
      <div className="flex justify-end mt-4">
        {method === "bank_transfer" ? (
          <button data-testid="bank-invoice-btn" disabled={busy} onClick={onBank} className="inline-flex items-center gap-1.5 bg-[#133326] hover:bg-[#0F281E] text-white text-sm px-4 py-2.5 rounded-md disabled:opacity-60">
            <Receipt className="w-4 h-4" /> {busy ? "Creating…" : "Generate bank invoice"}
          </button>
        ) : (
          <button data-testid="stripe-btn" disabled={busy} onClick={onStripe} className="inline-flex items-center gap-1.5 bg-[#635BFF] hover:bg-[#4F46E5] text-white text-sm px-4 py-2.5 rounded-md disabled:opacity-60">
            <ExternalLink className="w-4 h-4" /> {busy ? "Redirecting…" : "Pay with Stripe"}
          </button>
        )}
      </div>
    </div>
  );
}

function PaymentOption({ active, onClick, icon: Icon, label, subtitle, badge, testid }) {
  return (
    <button data-testid={testid} onClick={onClick} className={`text-left border rounded-md p-3 transition ${active ? "border-[#26547C] bg-[#E5EEF6] ring-2 ring-[#26547C]" : "border-[#E2DFD6] hover:bg-[#F7F6F2]"}`}>
      <div className="flex items-center gap-2">
        <Icon className="w-5 h-5 text-[#133326]" strokeWidth={1.5} />
        <div className="font-medium">{label}</div>
      </div>
      <div className="text-xs text-[#525860] mt-1">{subtitle}</div>
      {badge && <span className="inline-block text-[9px] uppercase tracking-wider text-[#2D7A5D] mt-2">{badge}</span>}
    </button>
  );
}

function InvoicesTable({ invoices }) {
  return (
    <div className="bg-white border border-[#E2DFD6] rounded-lg overflow-hidden">
      <div className="px-6 py-3 border-b border-[#E2DFD6]">
        <h2 className="font-heading text-lg font-semibold">Invoice history</h2>
      </div>
      <table className="w-full text-sm">
        <thead className="bg-[#F7F6F2]">
          <tr>{["Reference", "Plan", "Amount", "Status", "Method", "Issued"].map((h) => (
            <th key={h} className="text-left text-[10px] uppercase tracking-wider text-[#525860] py-2.5 px-4 font-medium">{h}</th>
          ))}</tr>
        </thead>
        <tbody>
          {invoices.map((inv) => (
            <tr key={inv.id} className="border-t border-[#E2DFD6]">
              <td className="py-2 px-4 font-data text-xs">{inv.reference}</td>
              <td className="py-2 px-4">{inv.plan_label}</td>
              <td className="py-2 px-4 font-data">{fmtSLE(inv.total_sle)}</td>
              <td className="py-2 px-4">
                <StatusPill status={inv.status} />
              </td>
              <td className="py-2 px-4 text-xs">{inv.payment_method === "bank_transfer" ? "Bank" : "Stripe"}</td>
              <td className="py-2 px-4 text-xs text-[#525860]">{new Date(inv.created_at).toLocaleDateString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function StatusPill({ status }) {
  const map = {
    open: { bg: "bg-[#FBF1DE]", fg: "text-[#8B6A14]", icon: Clock, label: "Open" },
    paid: { bg: "bg-[#E6F4EC]", fg: "text-[#2D7A5D]", icon: Check, label: "Paid" },
    cancelled: { bg: "bg-[#EBE8E0]", fg: "text-[#525860]", icon: X, label: "Cancelled" },
  };
  const p = map[status] || map.open;
  const Icon = p.icon;
  return (
    <span className={`inline-flex items-center gap-1 text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-full ${p.bg} ${p.fg}`}>
      <Icon className="w-3 h-3" /> {p.label}
    </span>
  );
}
