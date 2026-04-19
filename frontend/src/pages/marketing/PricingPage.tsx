import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, Check, ChevronDown, Droplet, Minus } from "lucide-react";
import { MarketingLayout } from "@/components/landing/MarketingLayout";
import { BorderBeam } from "@/components/lightswind/border-beam";

type Billing = "monthly" | "yearly";

interface PlanFeature {
  label: string;
  value: string | boolean;
}

interface Plan {
  id: "starter" | "growth" | "enterprise";
  name: string;
  tagline: string;
  monthly: number | null;
  yearly: number | null;
  priceLabel?: string;
  highlights: string[];
  cta: { label: string; to: string };
  popular?: boolean;
}

const PLANS: Plan[] = [
  {
    id: "starter",
    name: "Starter",
    tagline: "Single pump, single shift",
    monthly: 2999,
    yearly: 2399,
    highlights: [
      "1 pump",
      "Up to 5 users",
      "Daily reconciliation",
      "Nozzle readings & shift management",
      "Email support (1 business day)",
    ],
    cta: { label: "Request access", to: "/request-access" },
  },
  {
    id: "growth",
    name: "Growth",
    tagline: "Multi-shift, multi-pump operations",
    monthly: 7999,
    yearly: 6399,
    popular: true,
    highlights: [
      "Up to 5 pumps",
      "Up to 25 users",
      "Anomaly detection",
      "FMS integrations (HPCL, BPCL, IOCL)",
      "Priority support (same day)",
    ],
    cta: { label: "Request access", to: "/request-access" },
  },
  {
    id: "enterprise",
    name: "Enterprise",
    tagline: "Multi-location chains",
    monthly: null,
    yearly: null,
    priceLabel: "Custom",
    highlights: [
      "Unlimited pumps",
      "SSO (SAML / OIDC)",
      "Dedicated Customer Success Manager",
      "On-prem or private-cloud option",
      "Custom integrations + SLA",
    ],
    cta: { label: "Talk to us", to: "/contact" },
  },
];

interface CompareRow {
  label: string;
  values: [PlanFeature["value"], PlanFeature["value"], PlanFeature["value"]];
}

const COMPARE_ROWS: CompareRow[] = [
  { label: "Pumps included", values: ["1", "Up to 5", "Unlimited"] },
  { label: "User seats", values: ["5", "25", "Unlimited"] },
  { label: "Daily reconciliation", values: [true, true, true] },
  { label: "Shift & nozzle management", values: [true, true, true] },
  { label: "Cash handling ledger", values: [true, true, true] },
  { label: "Variance tracking", values: [true, true, true] },
  { label: "Anomaly detection", values: [false, true, true] },
  { label: "FMS integration (HPCL/BPCL/IOCL)", values: [false, true, true] },
  { label: "POS batch settlements", values: [false, true, true] },
  { label: "UPI transaction ingest", values: [false, true, true] },
  { label: "Audit trail export", values: [true, true, true] },
  { label: "API access", values: [false, true, true] },
  { label: "Role-based access control", values: [true, true, true] },
  { label: "SSO (SAML / OIDC)", values: [false, false, true] },
  { label: "Dedicated CSM", values: [false, false, true] },
  { label: "On-prem / private-cloud", values: [false, false, true] },
  { label: "Custom integrations", values: [false, false, true] },
  { label: "Uptime SLA", values: ["Best-effort", "99.5%", "99.9%"] },
  { label: "Support", values: ["Email", "Priority", "24x7 + CSM"] },
  { label: "Onboarding", values: ["Self-serve", "Guided", "White-glove"] },
];

const FAQS: { q: string; a: string }[] = [
  {
    q: "Can I change plans later?",
    a: "Absolutely. You can upgrade or downgrade at any time from inside the app and the change takes effect on your next billing cycle. We'll pro-rate any difference automatically.",
  },
  {
    q: "Is my data secure?",
    a: "Every tenant gets isolated storage with row-level enforcement on top of encryption at rest and TLS in transit. The Enterprise plan adds per-tenant key management and optional on-prem deployment.",
  },
  {
    q: "Do you offer onboarding?",
    a: "Yes. Starter gets a self-serve guide and email support. Growth includes a guided onboarding session with one of our engineers. Enterprise includes white-glove onboarding and a dedicated Customer Success Manager.",
  },
  {
    q: "What happens if I exceed my pump or user limit?",
    a: "We'll alert the account owner well before the hard limit is hit and suggest the next plan tier. Nothing stops working — we never cut off service mid-day.",
  },
  {
    q: "Do you support GST invoicing?",
    a: "Every invoice we generate is GST-compliant with your GSTIN, HSN codes and place of supply, and is downloadable as a signed PDF from inside the billing portal.",
  },
  {
    q: "How does billing work?",
    a: "Pay by UPI, NEFT, or card. Monthly plans auto-renew each month; yearly plans bill upfront and save 20%. Enterprise plans are billed against a custom purchase order and SLA.",
  },
];

function priceFor(plan: Plan, billing: Billing): string {
  if (plan.priceLabel) return plan.priceLabel;
  const amount = billing === "monthly" ? plan.monthly : plan.yearly;
  if (amount === null) return "—";
  return `₹${amount.toLocaleString("en-IN")}`;
}

function Cell({ value }: { value: PlanFeature["value"] }) {
  if (value === true) {
    return (
      <span className="inline-flex items-center justify-center">
        <Check className="h-4 w-4 text-emerald-400" />
      </span>
    );
  }
  if (value === false) {
    return (
      <span className="inline-flex items-center justify-center">
        <Minus className="h-4 w-4 text-slate-600" />
      </span>
    );
  }
  return <span className="text-sm text-slate-300">{value}</span>;
}

export default function PricingPage() {
  const [billing, setBilling] = useState<Billing>("monthly");

  const subhead = useMemo(
    () =>
      billing === "yearly"
        ? "Yearly pricing — save 20% vs. month-to-month."
        : "Simple monthly pricing. No setup fees. Cancel anytime.",
    [billing]
  );

  return (
    <MarketingLayout wide>
      {/* Hero */}
      <section className="relative overflow-hidden border-b border-white/5">
        <div className="absolute inset-0 pointer-events-none">
          <div className="absolute -top-40 left-1/2 -translate-x-1/2 h-[420px] w-[820px] rounded-full bg-amber-400/10 blur-[120px]" />
        </div>
        <div className="relative max-w-7xl mx-auto px-6 lg:px-8 py-20 md:py-24 text-center">
          <span className="inline-flex items-center gap-2 text-xs font-mono uppercase tracking-[0.22em] text-amber-400/80">
            <Droplet className="h-3.5 w-3.5" />
            Pricing
          </span>
          <h1 className="mt-5 font-display font-bold text-4xl md:text-6xl tracking-tight text-balance max-w-3xl mx-auto">
            Transparent pricing that scales with you.
          </h1>
          <p className="mt-5 text-lg md:text-xl text-slate-400 leading-relaxed max-w-2xl mx-auto text-pretty">
            {subhead}
          </p>

          {/* Toggle */}
          <div className="mt-10 inline-flex items-center p-1 rounded-full border border-white/10 bg-white/[0.03]">
            <button
              type="button"
              onClick={() => setBilling("monthly")}
              className={`h-9 px-5 rounded-full text-sm font-medium transition ${
                billing === "monthly"
                  ? "bg-white text-slate-950"
                  : "text-slate-300 hover:text-white"
              }`}
            >
              Monthly
            </button>
            <button
              type="button"
              onClick={() => setBilling("yearly")}
              className={`h-9 px-5 rounded-full text-sm font-medium transition flex items-center gap-2 ${
                billing === "yearly"
                  ? "bg-white text-slate-950"
                  : "text-slate-300 hover:text-white"
              }`}
            >
              Yearly
              <span
                className={`rounded-full px-2 py-0.5 text-[10px] font-mono uppercase tracking-wider ${
                  billing === "yearly"
                    ? "bg-emerald-400/20 text-emerald-700"
                    : "bg-emerald-400/15 text-emerald-300"
                }`}
              >
                Save 20%
              </span>
            </button>
          </div>
        </div>
      </section>

      {/* Plan cards */}
      <section className="relative">
        <div className="max-w-7xl mx-auto px-6 lg:px-8 py-16 md:py-20">
          <div className="grid md:grid-cols-3 gap-6 max-w-6xl mx-auto">
            {PLANS.map((p) => (
              <div
                key={p.id}
                className={`relative rounded-2xl border bg-slate-900/40 p-8 transition-all duration-300 ${
                  p.popular
                    ? "border-amber-400/40 md:scale-[1.02] shadow-glow-amber"
                    : "border-white/5 hover:border-white/10"
                }`}
              >
                {p.popular && (
                  <>
                    <BorderBeam
                      size={240}
                      duration={10}
                      colorFrom="#fbbf24"
                      colorTo="#34d399"
                    />
                    <div className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-amber-400 text-slate-950 text-[10px] font-mono uppercase tracking-[0.18em] px-3 py-1">
                      Most popular
                    </div>
                  </>
                )}
                <h3 className="font-display text-2xl font-semibold text-white">
                  {p.name}
                </h3>
                <p className="mt-1 text-sm text-slate-400">{p.tagline}</p>
                <div className="mt-6 flex items-baseline gap-2">
                  <span className="font-mono text-5xl font-bold text-white">
                    {priceFor(p, billing)}
                  </span>
                  {!p.priceLabel && (
                    <span className="text-slate-500 text-sm">
                      /{billing === "monthly" ? "month" : "mo, billed yearly"}
                    </span>
                  )}
                </div>
                {billing === "yearly" && !p.priceLabel && p.monthly && (
                  <div className="mt-1 text-xs font-mono text-slate-500">
                    <span className="line-through">
                      ₹{p.monthly.toLocaleString("en-IN")}
                    </span>
                    <span className="ml-2 text-emerald-400">You save 20%</span>
                  </div>
                )}
                <ul className="mt-8 space-y-3">
                  {p.highlights.map((f) => (
                    <li
                      key={f}
                      className="flex items-start gap-3 text-sm text-slate-300"
                    >
                      <Check className="h-4 w-4 text-emerald-400 mt-0.5 shrink-0" />
                      {f}
                    </li>
                  ))}
                </ul>
                <Link
                  to={p.cta.to}
                  className={`mt-8 inline-flex w-full items-center justify-center h-12 rounded-full font-medium transition-all duration-200 ${
                    p.popular
                      ? "bg-amber-400 text-slate-950 hover:bg-amber-300"
                      : "border border-white/10 bg-white/[0.03] text-white hover:bg-white/[0.06]"
                  }`}
                >
                  {p.cta.label}
                  <ArrowRight className="h-4 w-4 ml-2" />
                </Link>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Comparison table */}
      <section className="relative bg-slate-900/30 border-y border-white/5">
        <div className="max-w-7xl mx-auto px-6 lg:px-8 py-20 md:py-24">
          <div className="max-w-3xl">
            <span className="text-xs font-mono uppercase tracking-[0.22em] text-amber-400/80">
              Compare plans
            </span>
            <h2 className="mt-4 font-display font-bold text-3xl md:text-4xl tracking-tight text-balance">
              Every feature, side by side.
            </h2>
          </div>

          <div className="mt-10 overflow-x-auto rounded-2xl border border-white/10">
            <table className="w-full min-w-[720px] text-left border-collapse">
              <thead className="sticky top-0 z-10 bg-slate-950/90 backdrop-blur">
                <tr className="border-b border-white/10">
                  <th className="px-6 py-4 font-display text-sm font-semibold text-slate-300">
                    Feature
                  </th>
                  {PLANS.map((p) => (
                    <th
                      key={p.id}
                      className={`px-6 py-4 text-center font-display text-sm font-semibold ${
                        p.popular ? "text-amber-300" : "text-slate-300"
                      }`}
                    >
                      {p.name}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {COMPARE_ROWS.map((row, idx) => (
                  <tr
                    key={row.label}
                    className={`border-b border-white/5 ${
                      idx % 2 === 0 ? "bg-white/[0.01]" : ""
                    }`}
                  >
                    <td className="px-6 py-3.5 text-sm text-slate-300">
                      {row.label}
                    </td>
                    {row.values.map((v, i) => (
                      <td
                        key={i}
                        className="px-6 py-3.5 text-center align-middle"
                      >
                        <Cell value={v} />
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section className="relative">
        <div className="max-w-4xl mx-auto px-6 lg:px-8 py-20 md:py-24">
          <div className="text-center">
            <span className="text-xs font-mono uppercase tracking-[0.22em] text-amber-400/80">
              FAQ
            </span>
            <h2 className="mt-4 font-display font-bold text-3xl md:text-4xl tracking-tight text-balance">
              Questions, answered.
            </h2>
          </div>

          <div className="mt-12 divide-y divide-white/10 rounded-2xl border border-white/10 bg-white/[0.02]">
            {FAQS.map((f) => (
              <details
                key={f.q}
                className="group px-6 py-5 open:bg-white/[0.02] transition-colors"
              >
                <summary className="flex items-start justify-between gap-6 cursor-pointer list-none">
                  <span className="font-display text-base md:text-lg font-medium text-white">
                    {f.q}
                  </span>
                  <ChevronDown className="h-5 w-5 text-slate-400 shrink-0 mt-1 transition-transform group-open:rotate-180" />
                </summary>
                <p className="mt-3 text-sm md:text-base text-slate-400 leading-relaxed">
                  {f.a}
                </p>
              </details>
            ))}
          </div>
        </div>
      </section>

      {/* Closing CTA */}
      <section className="relative">
        <div className="max-w-5xl mx-auto px-6 lg:px-8 pb-20 md:pb-28">
          <div className="relative overflow-hidden rounded-3xl border border-white/10 bg-gradient-to-br from-slate-900 via-slate-950 to-slate-900 p-10 md:p-14 text-center">
            <div className="absolute inset-0 pointer-events-none">
              <div className="absolute -top-24 left-1/2 -translate-x-1/2 h-64 w-[600px] rounded-full bg-amber-400/10 blur-3xl" />
            </div>
            <div className="relative">
              <h2 className="font-display font-bold text-3xl md:text-5xl tracking-tight text-balance">
                Still not sure?
              </h2>
              <p className="mt-4 text-slate-400 text-lg max-w-xl mx-auto text-pretty">
                Talk to us. We'll walk through your numbers and recommend the right plan — no
                pressure, no sales script.
              </p>
              <div className="mt-8 flex flex-wrap justify-center items-center gap-3">
                <Link
                  to="/contact"
                  className="inline-flex items-center h-12 px-7 rounded-full bg-amber-400 text-slate-950 font-medium hover:bg-amber-300 transition shadow-glow-amber"
                >
                  Talk to us
                  <ArrowRight className="h-4 w-4 ml-2" />
                </Link>
                <Link
                  to="/features"
                  className="inline-flex items-center h-12 px-7 rounded-full border border-white/10 bg-white/[0.03] text-white hover:bg-white/[0.06] transition"
                >
                  See features
                </Link>
              </div>
            </div>
          </div>
        </div>
      </section>
    </MarketingLayout>
  );
}
