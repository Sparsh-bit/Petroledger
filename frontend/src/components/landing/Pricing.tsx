import { Link } from "react-router-dom";
import { Check } from "lucide-react";
import { BorderBeam } from "@/components/lightswind/border-beam";

const PLANS = [
  {
    name: "Starter",
    price: 1499,
    desc: "Single pump, single shift",
    features: ["1 outlet", "Up to 4 nozzles", "Daily reconciliation", "Email support"],
    popular: false,
  },
  {
    name: "Growth",
    price: 3999,
    desc: "Multi-shift operations",
    features: [
      "Up to 3 outlets",
      "Unlimited nozzles",
      "FMS integrations",
      "Variance alerts",
      "Priority support",
    ],
    popular: true,
  },
  {
    name: "Enterprise",
    price: 9999,
    desc: "Multi-location chain",
    features: [
      "Unlimited outlets",
      "Custom roles & SSO",
      "Dedicated success manager",
      "API access",
      "On-call SLA",
    ],
    popular: false,
  },
];

export function Pricing() {
  return (
    <section id="pricing" className="relative">
      <div className="max-w-7xl mx-auto px-6 lg:px-8 py-20 md:py-32">
        <div className="max-w-3xl mx-auto text-center">
          <span className="text-xs font-mono uppercase tracking-[0.2em] text-amber-400/80">
            Pricing
          </span>
          <h2 className="mt-4 font-display font-bold text-4xl md:text-5xl tracking-tight text-balance">
            Plans that scale with your stations.
          </h2>
          <p className="mt-5 text-slate-400 text-lg leading-relaxed">
            Simple monthly pricing. No setup fees. Cancel anytime.
          </p>
        </div>

        <div className="mt-16 grid md:grid-cols-3 gap-6 max-w-6xl mx-auto">
          {PLANS.map((p) => (
            <div
              key={p.name}
              className={`relative rounded-2xl border bg-slate-900/40 p-8 transition-all duration-300 ${
                p.popular
                  ? "border-amber-400/40 md:scale-105 shadow-glow-amber"
                  : "border-white/5 hover:border-white/10"
              }`}
            >
              {p.popular && (
                <>
                  <BorderBeam size={250} duration={10} colorFrom="#fbbf24" colorTo="#34d399" />
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-amber-400 text-slate-950 text-[10px] font-mono uppercase tracking-[0.18em] px-3 py-1">
                    Most popular
                  </div>
                </>
              )}
              <h3 className="font-display text-2xl font-semibold text-white">{p.name}</h3>
              <p className="mt-1 text-sm text-slate-400">{p.desc}</p>
              <div className="mt-6 flex items-baseline gap-2">
                <span className="font-mono text-5xl font-bold text-white">
                  ₹{p.price.toLocaleString("en-IN")}
                </span>
                <span className="text-slate-500 text-sm">/month</span>
              </div>
              <ul className="mt-8 space-y-3">
                {p.features.map((f) => (
                  <li key={f} className="flex items-start gap-3 text-sm text-slate-300">
                    <Check className="h-4 w-4 text-emerald-400 mt-0.5 shrink-0" />
                    {f}
                  </li>
                ))}
              </ul>
              <Link
                to="/login"
                className={`mt-8 inline-flex w-full items-center justify-center h-12 rounded-full font-medium transition-all duration-200 ${
                  p.popular
                    ? "bg-amber-400 text-slate-950 hover:bg-amber-300"
                    : "border border-white/10 bg-white/[0.03] text-white hover:bg-white/[0.06]"
                }`}
              >
                {p.popular ? "Start free trial" : "Choose plan"}
              </Link>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
