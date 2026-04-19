import { Link } from "react-router-dom";
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  BarChart3,
  Building2,
  CheckCheck,
  ClipboardList,
  Database,
  Droplet,
  Fingerprint,
  Gauge,
  KeyRound,
  Layers,
  Lock,
  Network,
  Plug,
  Receipt,
  ScanLine,
  ShieldCheck,
  TrendingUp,
  Truck,
  Users,
  Wallet,
} from "lucide-react";
import { MarketingLayout } from "@/components/landing/MarketingLayout";

interface FeatureCard {
  icon: typeof BarChart3;
  title: string;
  text: string;
}

interface FeatureGroup {
  id: string;
  eyebrow: string;
  title: string;
  blurb: string;
  items: FeatureCard[];
}

const GROUPS: FeatureGroup[] = [
  {
    id: "operations",
    eyebrow: "Operations",
    title: "Run every shift with confidence",
    blurb:
      "The day-to-day toolkit owners, managers and workers rely on — from opening dip to closing cash count.",
    items: [
      {
        icon: CheckCheck,
        title: "Daily Reconciliation",
        text: "Match nozzle sales, POS settlements, UPI and cash against meters — automatically, every single day.",
      },
      {
        icon: Users,
        title: "Multi-Role Access",
        text: "Owner, Admin, Manager and Worker portals, each scoped to exactly what that role needs to see.",
      },
      {
        icon: ClipboardList,
        title: "Shift Management",
        text: "Open and close shifts with meter snapshots, hand-over notes and automatic variance flags.",
      },
      {
        icon: Gauge,
        title: "Nozzle Readings",
        text: "Capture opening and closing totalizers with unit checks and duplicate-read protection built in.",
      },
      {
        icon: Wallet,
        title: "Cash Handling",
        text: "Track denomination-wise cash counts, short-cash incidents and hand-overs with a clean audit trail.",
      },
    ],
  },
  {
    id: "intelligence",
    eyebrow: "Intelligence",
    title: "Catch problems before they cost you",
    blurb:
      "Signals, not spreadsheets. We highlight the outliers so owners spend minutes — not hours — on the closing.",
    items: [
      {
        icon: AlertTriangle,
        title: "Anomaly Detection",
        text: "Detect density drift, missing deliveries, suspicious credit patterns and off-hours entries automatically.",
      },
      {
        icon: Activity,
        title: "Real-time Analytics",
        text: "Sales, dips, credit and shift performance refreshed live — no overnight batch jobs to wait on.",
      },
      {
        icon: TrendingUp,
        title: "Variance Tracking",
        text: "Track volumetric and financial variances by nozzle, shift and worker, with trend lines over time.",
      },
      {
        icon: ScanLine,
        title: "Audit Trail",
        text: "Every edit is timestamped, attributed and signed — exportable to your auditor in a single click.",
      },
    ],
  },
  {
    id: "integrations",
    eyebrow: "Integrations",
    title: "Connected to the systems you already use",
    blurb:
      "PetroLedger speaks fluent OMC, POS and UPI — so the numbers line up without copy-paste gymnastics.",
    items: [
      {
        icon: Truck,
        title: "FMS Integration",
        text: "Ingest HPCL, BPCL and IOCL fleet-management feeds directly — no more CSV juggling on Monday mornings.",
      },
      {
        icon: Receipt,
        title: "POS Batch Settlements",
        text: "Match daily POS batches from every terminal against your ledger with auto-exception handling.",
      },
      {
        icon: Plug,
        title: "UPI Transactions",
        text: "Pull UPI collections with VPA and RRN so every rupee reconciles end-to-end without guesswork.",
      },
      {
        icon: Database,
        title: "Data Ingestion",
        text: "CSV, XLSX and email-dropbox ingestion with mapping rules — so legacy feeds keep working on day one.",
      },
    ],
  },
  {
    id: "platform",
    eyebrow: "Platform",
    title: "Enterprise-grade foundation, dealer-friendly price",
    blurb:
      "Built multi-tenant from the first commit, with the security posture a chain owner expects.",
    items: [
      {
        icon: Building2,
        title: "Multi-tenancy",
        text: "Every organization gets isolated data, users, roles and FMS connections — no cross-tenant leakage ever.",
      },
      {
        icon: KeyRound,
        title: "Role-based Access",
        text: "Fine-grained permissions for Owner, Admin, Manager and Worker — tailored to real pump operations.",
      },
      {
        icon: Network,
        title: "API-first",
        text: "A documented REST API underneath every screen — perfect for chain-wide dashboards and custom BI.",
      },
      {
        icon: Fingerprint,
        title: "Enterprise SSO-ready",
        text: "Plug in SAML or OIDC identity providers on the Enterprise plan — centralized login for chain staff.",
      },
    ],
  },
];

interface DeepDive {
  title: string;
  eyebrow: string;
  body: string;
  bullets: string[];
  icon: typeof BarChart3;
  accent: string;
}

const DEEP_DIVES: DeepDive[] = [
  {
    eyebrow: "Daily Reconciliation",
    title: "Close the day in minutes, not hours",
    icon: BarChart3,
    accent: "from-amber-400/25 to-amber-500/10",
    body:
      "PetroLedger automatically assembles every source that moves money — nozzle totalizers, POS batches, UPI collections, fleet-card claims and physical cash declarations — and matches them into a single reconciled day. Variances surface with the exact line item that caused them, so your manager can action the exception instead of hunting through paper logbooks. Owners see the closed-out day on their phone by 10pm, not 10am the next morning.",
    bullets: [
      "Source-to-source matching across five data feeds",
      "Exception drill-down to the nozzle and shift level",
      "Same-day close with signed audit events",
    ],
  },
  {
    eyebrow: "Anomaly Detection",
    title: "Spot shrinkage the same day it happens",
    icon: AlertTriangle,
    accent: "from-rose-400/25 to-rose-500/10",
    body:
      "Silent losses are the single biggest pain for dealer-owned pumps. PetroLedger watches density drift, short-deliveries, off-hours entries, repeated manual over-rides and credit-party overshoot, and surfaces each with a plain-English reason. You don't have to know statistics — you just get a short list of things to look at, ranked by rupee impact. Most owners clear the list in under ten minutes every evening.",
    bullets: [
      "Density, volume, cash and credit anomaly models",
      "Ranked by financial impact, not alert count",
      "Every alert links back to the underlying evidence",
    ],
  },
  {
    eyebrow: "Multi-Role Access",
    title: "Right information, right person, every time",
    icon: Users,
    accent: "from-emerald-400/25 to-emerald-500/10",
    body:
      "PetroLedger ships with purpose-built portals for Owner, Admin, Manager and Worker — each with its own information density and permissions. Workers only see their own shift and readings. Managers see the day. Admins see the month. Owners see the chain. Access is enforced on the server, so nothing leaks in the browser. Onboarding a new worker takes under a minute and does not require any spreadsheet sharing.",
    bullets: [
      "Four role templates out of the box",
      "Server-side permission enforcement, not just UI",
      "Per-user activity log with searchable history",
    ],
  },
];

const STATS = [
  { value: "< 1 hr", label: "Typical daily close time" },
  { value: "99.9%", label: "Tenant-isolated uptime target" },
  { value: "5", label: "Data feeds reconciled per day" },
  { value: "100%", label: "Signed, exportable audit trail" },
];

export default function FeaturesPage() {
  return (
    <MarketingLayout wide>
      {/* Hero */}
      <section className="relative overflow-hidden border-b border-white/5">
        <div className="absolute inset-0 pointer-events-none">
          <div className="absolute -top-40 left-1/2 -translate-x-1/2 h-[420px] w-[820px] rounded-full bg-amber-400/10 blur-[120px]" />
        </div>
        <div className="relative max-w-7xl mx-auto px-6 lg:px-8 py-20 md:py-28">
          <div className="max-w-3xl">
            <span className="inline-flex items-center gap-2 text-xs font-mono uppercase tracking-[0.22em] text-amber-400/80">
              <Droplet className="h-3.5 w-3.5" />
              Features
            </span>
            <h1 className="mt-5 font-display font-bold text-4xl md:text-6xl tracking-tight text-balance">
              Everything a modern petrol pump needs.
            </h1>
            <p className="mt-6 text-lg md:text-xl text-slate-400 leading-relaxed text-pretty max-w-2xl">
              From daily reconciliation to anomaly detection to OMC integrations — PetroLedger
              bundles every tool a dealer-owned pump needs to run with the same discipline as a
              modern retail business.
            </p>
            <div className="mt-8 flex flex-wrap items-center gap-3">
              <Link
                to="/request-access"
                className="inline-flex items-center h-11 px-6 rounded-full bg-amber-400 text-slate-950 font-medium hover:bg-amber-300 transition shadow-glow-amber"
              >
                Request access
                <ArrowRight className="h-4 w-4 ml-2" />
              </Link>
              <Link
                to="/pricing"
                className="inline-flex items-center h-11 px-6 rounded-full border border-white/10 bg-white/[0.03] text-white hover:bg-white/[0.06] transition"
              >
                See pricing
              </Link>
            </div>
          </div>

          <div className="mt-16 grid grid-cols-2 md:grid-cols-4 gap-4">
            {STATS.map((s) => (
              <div
                key={s.label}
                className="rounded-2xl border border-white/5 bg-white/[0.02] p-5"
              >
                <div className="font-mono text-2xl md:text-3xl font-bold text-white">
                  {s.value}
                </div>
                <div className="mt-2 text-xs uppercase tracking-wider text-slate-500">
                  {s.label}
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Feature groups */}
      {GROUPS.map((g, idx) => (
        <section
          key={g.id}
          id={g.id}
          className={`relative ${idx % 2 === 1 ? "bg-slate-900/30 border-y border-white/5" : ""}`}
        >
          <div className="max-w-7xl mx-auto px-6 lg:px-8 py-20 md:py-24">
            <div className="grid md:grid-cols-[0.9fr_2fr] gap-10 items-start">
              <div className="md:sticky md:top-28">
                <span className="text-xs font-mono uppercase tracking-[0.22em] text-amber-400/80">
                  {g.eyebrow}
                </span>
                <h2 className="mt-4 font-display font-bold text-3xl md:text-4xl tracking-tight text-balance">
                  {g.title}
                </h2>
                <p className="mt-4 text-slate-400 leading-relaxed text-pretty">
                  {g.blurb}
                </p>
              </div>

              <div className="grid sm:grid-cols-2 gap-4">
                {g.items.map((f) => {
                  const Icon = f.icon;
                  return (
                    <div
                      key={f.title}
                      className="group rounded-2xl border border-white/5 bg-white/[0.02] hover:bg-white/[0.04] hover:border-white/10 p-6 transition-all duration-300"
                    >
                      <div className="inline-flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br from-amber-400/20 to-emerald-400/20 ring-1 ring-white/10">
                        <Icon className="h-5 w-5 text-amber-300" />
                      </div>
                      <h3 className="mt-5 font-display text-lg font-semibold text-white">
                        {f.title}
                      </h3>
                      <p className="mt-2 text-sm text-slate-400 leading-relaxed">
                        {f.text}
                      </p>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </section>
      ))}

      {/* Deep dives */}
      <section className="relative">
        <div className="max-w-7xl mx-auto px-6 lg:px-8 py-20 md:py-28">
          <div className="max-w-3xl">
            <span className="text-xs font-mono uppercase tracking-[0.22em] text-amber-400/80">
              Under the hood
            </span>
            <h2 className="mt-4 font-display font-bold text-3xl md:text-5xl tracking-tight text-balance">
              Three features worth a closer look.
            </h2>
            <p className="mt-4 text-slate-400 text-lg leading-relaxed text-pretty">
              The bits of PetroLedger that customers tell us pay for the subscription on their own.
            </p>
          </div>

          <div className="mt-16 space-y-20">
            {DEEP_DIVES.map((d, idx) => {
              const Icon = d.icon;
              const flipped = idx % 2 === 1;
              return (
                <div
                  key={d.title}
                  className={`grid md:grid-cols-2 gap-10 md:gap-16 items-center ${
                    flipped ? "md:[&>:first-child]:order-2" : ""
                  }`}
                >
                  <div>
                    <span className="text-xs font-mono uppercase tracking-[0.22em] text-amber-400/80">
                      {d.eyebrow}
                    </span>
                    <h3 className="mt-4 font-display font-bold text-2xl md:text-4xl tracking-tight text-balance">
                      {d.title}
                    </h3>
                    <p className="mt-5 text-slate-400 leading-relaxed text-pretty">
                      {d.body}
                    </p>
                    <ul className="mt-6 space-y-2.5">
                      {d.bullets.map((b) => (
                        <li
                          key={b}
                          className="flex items-start gap-3 text-sm text-slate-300"
                        >
                          <CheckCheck className="h-4 w-4 text-emerald-400 mt-0.5 shrink-0" />
                          {b}
                        </li>
                      ))}
                    </ul>
                  </div>

                  <div className="relative">
                    <div
                      className={`relative rounded-3xl border border-white/10 bg-gradient-to-br ${d.accent} p-10 overflow-hidden`}
                    >
                      <div className="absolute -top-12 -right-12 h-48 w-48 rounded-full bg-white/5 blur-3xl" />
                      <div className="relative flex items-center gap-4">
                        <span className="inline-flex h-14 w-14 items-center justify-center rounded-2xl bg-slate-950/60 ring-1 ring-white/10">
                          <Icon className="h-7 w-7 text-amber-300" />
                        </span>
                        <div>
                          <div className="text-xs font-mono uppercase tracking-[0.2em] text-slate-400">
                            Module
                          </div>
                          <div className="font-display text-lg font-semibold text-white">
                            {d.eyebrow}
                          </div>
                        </div>
                      </div>

                      <div className="relative mt-8 rounded-2xl border border-white/10 bg-slate-950/50 p-5">
                        <div className="flex items-center justify-between text-[10px] font-mono uppercase tracking-[0.2em] text-slate-500">
                          <span>Live sample</span>
                          <span className="flex items-center gap-1.5 text-emerald-400">
                            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
                            Synced
                          </span>
                        </div>
                        <div className="mt-4 space-y-2.5">
                          {[0, 1, 2, 3].map((row) => (
                            <div
                              key={row}
                              className="flex items-center gap-3 rounded-lg bg-white/[0.03] border border-white/5 px-3 py-2.5"
                            >
                              <span className="h-2 w-2 rounded-full bg-amber-400" />
                              <div className="flex-1 h-2 rounded-full bg-white/10 overflow-hidden">
                                <div
                                  className="h-full bg-gradient-to-r from-amber-400 to-emerald-400"
                                  style={{
                                    width: `${60 + (row * 8) % 35}%`,
                                  }}
                                />
                              </div>
                              <span className="font-mono text-xs text-slate-400">
                                {(2450 + row * 317).toLocaleString("en-IN")}
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* Trust band */}
      <section className="relative border-y border-white/5 bg-slate-900/30">
        <div className="max-w-7xl mx-auto px-6 lg:px-8 py-16">
          <div className="grid md:grid-cols-3 gap-6">
            {[
              {
                icon: ShieldCheck,
                title: "Built for Indian compliance",
                text: "GST-ready invoicing, timestamped ledgers and SROs that keep your auditor happy.",
              },
              {
                icon: Lock,
                title: "Encrypted, isolated, audited",
                text: "Per-tenant encryption keys, row-level isolation and full action history on every record.",
              },
              {
                icon: Layers,
                title: "Scales from 1 to 100 pumps",
                text: "Same product for single-pump dealers and multi-state chains — pay only for what you use.",
              },
            ].map((t) => {
              const Icon = t.icon;
              return (
                <div
                  key={t.title}
                  className="rounded-2xl border border-white/5 bg-white/[0.02] p-6"
                >
                  <Icon className="h-6 w-6 text-emerald-400" />
                  <h4 className="mt-4 font-display text-lg font-semibold text-white">
                    {t.title}
                  </h4>
                  <p className="mt-2 text-sm text-slate-400 leading-relaxed">
                    {t.text}
                  </p>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* Closing CTA */}
      <section className="relative">
        <div className="max-w-5xl mx-auto px-6 lg:px-8 py-20 md:py-28">
          <div className="relative overflow-hidden rounded-3xl border border-white/10 bg-gradient-to-br from-slate-900 via-slate-950 to-slate-900 p-10 md:p-16 text-center">
            <div className="absolute inset-0 pointer-events-none">
              <div className="absolute -top-24 left-1/2 -translate-x-1/2 h-64 w-[600px] rounded-full bg-amber-400/10 blur-3xl" />
            </div>
            <div className="relative">
              <h2 className="font-display font-bold text-3xl md:text-5xl tracking-tight text-balance">
                Ready to see it on your pump?
              </h2>
              <p className="mt-4 text-slate-400 text-lg max-w-xl mx-auto text-pretty">
                Request access and we'll provision your tenant, import your pumps and get you live
                inside a week.
              </p>
              <div className="mt-8 flex flex-wrap justify-center items-center gap-3">
                <Link
                  to="/request-access"
                  className="inline-flex items-center h-12 px-7 rounded-full bg-amber-400 text-slate-950 font-medium hover:bg-amber-300 transition shadow-glow-amber"
                >
                  Request access
                  <ArrowRight className="h-4 w-4 ml-2" />
                </Link>
                <Link
                  to="/contact"
                  className="inline-flex items-center h-12 px-7 rounded-full border border-white/10 bg-white/[0.03] text-white hover:bg-white/[0.06] transition"
                >
                  Talk to us
                </Link>
              </div>
            </div>
          </div>
        </div>
      </section>
    </MarketingLayout>
  );
}
