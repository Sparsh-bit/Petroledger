import { Link } from "react-router-dom";
import {
  ArrowRight,
  Award,
  CalendarClock,
  CheckCheck,
  Compass,
  Droplet,
  GraduationCap,
  Headphones,
  LayoutGrid,
  LifeBuoy,
  Rocket,
  Settings2,
  ShieldCheck,
  UserPlus,
  Users,
} from "lucide-react";
import { MarketingLayout } from "@/components/landing/MarketingLayout";

interface Step {
  n: string;
  day: string;
  title: string;
  icon: typeof Rocket;
  body: string;
  kpi: { label: string; value: string };
  checks: string[];
}

const STEPS: Step[] = [
  {
    n: "01",
    day: "Day 1",
    title: "Discover",
    icon: Compass,
    body:
      "We kick off with a 30-minute demo call tailored to your pump layout. You share the basics — number of pumps, nozzles, OMC, shift pattern, existing tools — and we scope the rollout. We confirm whether the Starter, Growth or Enterprise plan fits, and send across a written scoping note so nothing gets lost in translation. No payment changes hands at this stage; the goal is simply to agree on what good looks like before we provision anything.",
    kpi: { label: "Scoping call duration", value: "30 min" },
    checks: [
      "30-minute demo + scoping call",
      "Plan recommendation in writing",
      "No payment at this stage",
    ],
  },
  {
    n: "02",
    day: "Day 2 – 3",
    title: "Onboard",
    icon: UserPlus,
    body:
      "Our team provisions your isolated tenant and imports your pump and nozzle configuration straight from the scoping note. We create the owner account first, then staff accounts against the role matrix you provided. You'll get a welcome pack with logins, quick-start videos and a calendar invite for the training session. Most single-pump dealers are fully provisioned by lunchtime on Day 2; multi-pump chains typically wrap by Day 3.",
    kpi: { label: "Average provisioning time", value: "4 hours" },
    checks: [
      "Dedicated tenant with owner + staff accounts",
      "Pumps and nozzles imported to match your layout",
      "Welcome pack with logins and training invite",
    ],
  },
  {
    n: "03",
    day: "Day 3 – 4",
    title: "Configure",
    icon: Settings2,
    body:
      "We sit with the Admin to define the non-obvious bits — shift rules, variance thresholds per product, anomaly sensitivity, cash-count templates, credit-party lists and tax codes. Where FMS integration is in scope, we obtain OMC credentials and light up HPCL, BPCL or IOCL feeds. POS batch and UPI feeds are configured at the same time so the first reconciliation run has real data to work with.",
    kpi: { label: "Typical configuration depth", value: "28 settings" },
    checks: [
      "Shift rules and variance thresholds",
      "FMS, POS and UPI feed connections",
      "Credit parties, tax codes and cash templates",
    ],
  },
  {
    n: "04",
    day: "Day 4 – 5",
    title: "Train",
    icon: GraduationCap,
    body:
      "We run a one-hour live training for the owner and on-site manager, recorded for replay. Workers get in-app tours the first time they log in — no classroom session required — and a set of printable quick-reference cards for the forecourt. Every role walks away knowing the three or four screens they actually need to use. Questions that come up during training become the first tickets in your shared support channel.",
    kpi: { label: "Training videos included", value: "12" },
    checks: [
      "1-hour live training for owner + manager",
      "In-app tours for every worker role",
      "Printable quick-reference cards",
    ],
  },
  {
    n: "05",
    day: "Day 5+",
    title: "Go live",
    icon: Rocket,
    body:
      "From day five, daily reconciliation runs automatically at close of business. Variances and anomalies surface on the owner dashboard overnight, with a ranked action list ready by 7 am. Our team monitors the first two closings alongside you — silently, unless something needs attention — and stays on standby through the first full month. After thirty days, you're self-sufficient, with support a chat message away.",
    kpi: { label: "First full close", value: "Day 5" },
    checks: [
      "Automatic daily reconciliation",
      "Anomaly dashboard live from day one",
      "White-glove monitoring for the first month",
    ],
  },
];

const DAY_ONE_ITEMS = [
  "All your pumps and nozzles live on the dashboard",
  "Role-based logins for every worker on your roster",
  "Daily reconciliation dashboard with yesterday's close",
  "Anomaly feed ranked by rupee impact",
  "FMS feeds from HPCL, BPCL or IOCL flowing in",
  "POS batch matching across every terminal",
  "UPI collections reconciled by VPA and RRN",
  "Shift open/close flow on the worker phone app",
  "Full audit trail with signed, exportable entries",
];

const SUPPORT_CARDS = [
  {
    icon: Headphones,
    title: "Email support",
    text: "Every plan includes email support with a one-business-day SLA. We log every ticket against your tenant so history is never lost.",
    badge: "All plans",
  },
  {
    icon: ShieldCheck,
    title: "Priority SLA",
    text: "Growth customers get same-day response and a priority queue for incidents that touch reconciliation or billing.",
    badge: "Growth",
  },
  {
    icon: LifeBuoy,
    title: "Dedicated CSM",
    text: "Enterprise customers work with a named Customer Success Manager, quarterly business reviews, and 24x7 incident cover.",
    badge: "Enterprise",
  },
];

const GUARANTEES = [
  {
    icon: CalendarClock,
    title: "Live in under a week",
    text: "Most pumps close their first reconciled day within five business days of signing.",
  },
  {
    icon: Users,
    title: "Single point of contact",
    text: "One named engineer carries your rollout end-to-end — no ticket handoffs, no re-explaining.",
  },
  {
    icon: Award,
    title: "30-day white glove",
    text: "We monitor your first month of closings and jump in silently if anything needs attention.",
  },
];

export default function HowItWorksPage() {
  return (
    <MarketingLayout wide>
      {/* Hero */}
      <section className="relative overflow-hidden border-b border-white/5">
        <div className="absolute inset-0 pointer-events-none">
          <div className="absolute -top-40 left-1/2 -translate-x-1/2 h-[420px] w-[820px] rounded-full bg-emerald-400/10 blur-[120px]" />
        </div>
        <div className="relative max-w-7xl mx-auto px-6 lg:px-8 py-20 md:py-28">
          <div className="max-w-3xl">
            <span className="inline-flex items-center gap-2 text-xs font-mono uppercase tracking-[0.22em] text-amber-400/80">
              <Droplet className="h-3.5 w-3.5" />
              How it works
            </span>
            <h1 className="mt-5 font-display font-bold text-4xl md:text-6xl tracking-tight text-balance">
              From zero to live in under a week.
            </h1>
            <p className="mt-6 text-lg md:text-xl text-slate-400 leading-relaxed text-pretty max-w-2xl">
              Five clear steps, a named engineer on your rollout, and a first reconciled close
              inside five business days. No rushed migrations, no months of consulting.
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
                to="/features"
                className="inline-flex items-center h-11 px-6 rounded-full border border-white/10 bg-white/[0.03] text-white hover:bg-white/[0.06] transition"
              >
                See features
              </Link>
            </div>
          </div>

          <div className="mt-16 grid grid-cols-1 md:grid-cols-3 gap-4">
            {GUARANTEES.map((g) => {
              const Icon = g.icon;
              return (
                <div
                  key={g.title}
                  className="rounded-2xl border border-white/5 bg-white/[0.02] p-6"
                >
                  <Icon className="h-6 w-6 text-amber-300" />
                  <h3 className="mt-4 font-display text-lg font-semibold text-white">
                    {g.title}
                  </h3>
                  <p className="mt-2 text-sm text-slate-400 leading-relaxed">
                    {g.text}
                  </p>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* Timeline */}
      <section className="relative">
        <div className="max-w-6xl mx-auto px-6 lg:px-8 py-20 md:py-28">
          <div className="max-w-3xl">
            <span className="text-xs font-mono uppercase tracking-[0.22em] text-amber-400/80">
              The five steps
            </span>
            <h2 className="mt-4 font-display font-bold text-3xl md:text-5xl tracking-tight text-balance">
              A week that earns its keep.
            </h2>
            <p className="mt-4 text-slate-400 text-lg leading-relaxed text-pretty">
              Each step is owned by a named engineer. You always know who to call and what happens
              next.
            </p>
          </div>

          <div className="mt-16 relative">
            {/* vertical spine */}
            <div
              aria-hidden
              className="hidden md:block absolute top-0 bottom-0 left-1/2 -translate-x-1/2 w-px bg-gradient-to-b from-transparent via-amber-400/30 to-transparent"
            />

            <ol className="space-y-16 md:space-y-24">
              {STEPS.map((s, idx) => {
                const flipped = idx % 2 === 1;
                const Icon = s.icon;
                return (
                  <li
                    key={s.n}
                    className={`grid md:grid-cols-2 gap-8 md:gap-12 items-center ${
                      flipped ? "md:[&>:first-child]:order-2" : ""
                    }`}
                  >
                    {/* number side */}
                    <div
                      className={`flex ${
                        flipped ? "md:justify-start" : "md:justify-end"
                      } justify-center`}
                    >
                      <div className="relative">
                        <div className="relative z-10 flex h-32 w-32 md:h-44 md:w-44 items-center justify-center rounded-full border border-amber-400/40 bg-slate-950 font-mono font-bold text-amber-400 text-5xl md:text-6xl shadow-[0_0_60px_-10px_rgba(251,191,36,0.35)]">
                          {s.n}
                        </div>
                        <div
                          aria-hidden
                          className="absolute inset-0 rounded-full bg-amber-400/10 blur-2xl"
                        />
                      </div>
                    </div>

                    {/* content side */}
                    <div>
                      <div className="flex items-center gap-3">
                        <span className="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-amber-400/20 to-emerald-400/20 ring-1 ring-white/10">
                          <Icon className="h-5 w-5 text-amber-300" />
                        </span>
                        <span className="text-xs font-mono uppercase tracking-[0.22em] text-slate-400">
                          {s.day}
                        </span>
                      </div>
                      <h3 className="mt-4 font-display font-bold text-3xl md:text-4xl tracking-tight text-white">
                        {s.title}
                      </h3>
                      <p className="mt-4 text-slate-400 leading-relaxed text-pretty">
                        {s.body}
                      </p>

                      <div className="mt-6 inline-flex items-center gap-3 rounded-full border border-amber-400/30 bg-amber-400/5 px-4 py-2">
                        <span className="text-[10px] font-mono uppercase tracking-[0.2em] text-amber-300/80">
                          {s.kpi.label}
                        </span>
                        <span className="font-mono text-sm font-semibold text-amber-200">
                          {s.kpi.value}
                        </span>
                      </div>

                      <ul className="mt-6 space-y-2.5">
                        {s.checks.map((c) => (
                          <li
                            key={c}
                            className="flex items-start gap-3 text-sm text-slate-300"
                          >
                            <CheckCheck className="h-4 w-4 text-emerald-400 mt-0.5 shrink-0" />
                            {c}
                          </li>
                        ))}
                      </ul>
                    </div>
                  </li>
                );
              })}
            </ol>
          </div>
        </div>
      </section>

      {/* Day-one panel */}
      <section className="relative bg-slate-900/30 border-y border-white/5">
        <div className="max-w-7xl mx-auto px-6 lg:px-8 py-20 md:py-24">
          <div className="grid md:grid-cols-[1fr_1.4fr] gap-10 items-start">
            <div>
              <span className="text-xs font-mono uppercase tracking-[0.22em] text-amber-400/80">
                Day one
              </span>
              <h2 className="mt-4 font-display font-bold text-3xl md:text-4xl tracking-tight text-balance">
                What you get on day one.
              </h2>
              <p className="mt-4 text-slate-400 leading-relaxed text-pretty">
                The moment your first close lands, here's what every stakeholder can touch —
                without waiting for a follow-up rollout phase.
              </p>
              <div className="mt-6 inline-flex items-center gap-2 text-xs font-mono uppercase tracking-[0.2em] text-emerald-300">
                <LayoutGrid className="h-4 w-4" />
                9 things, live on day 5
              </div>
            </div>

            <div className="rounded-3xl border border-white/10 bg-gradient-to-br from-slate-900 via-slate-950 to-slate-900 p-8 md:p-10">
              <ul className="grid sm:grid-cols-2 gap-3">
                {DAY_ONE_ITEMS.map((item, idx) => (
                  <li
                    key={item}
                    className="flex items-start gap-3 rounded-xl border border-white/5 bg-white/[0.02] p-4"
                  >
                    <span className="font-mono text-xs font-semibold text-amber-300 w-6 shrink-0">
                      {String(idx + 1).padStart(2, "0")}
                    </span>
                    <span className="text-sm text-slate-200 leading-relaxed">
                      {item}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      </section>

      {/* Ongoing support */}
      <section className="relative">
        <div className="max-w-7xl mx-auto px-6 lg:px-8 py-20 md:py-24">
          <div className="max-w-3xl">
            <span className="text-xs font-mono uppercase tracking-[0.22em] text-amber-400/80">
              Ongoing support
            </span>
            <h2 className="mt-4 font-display font-bold text-3xl md:text-4xl tracking-tight text-balance">
              We don't disappear after go-live.
            </h2>
            <p className="mt-4 text-slate-400 leading-relaxed text-pretty">
              Pick the level of hand-holding that matches how your chain runs.
            </p>
          </div>

          <div className="mt-12 grid md:grid-cols-3 gap-6">
            {SUPPORT_CARDS.map((c) => {
              const Icon = c.icon;
              return (
                <div
                  key={c.title}
                  className="relative rounded-2xl border border-white/10 bg-white/[0.02] p-8 hover:border-white/20 transition"
                >
                  <div className="absolute top-5 right-5 rounded-full bg-amber-400/10 text-amber-300 text-[10px] font-mono uppercase tracking-[0.18em] px-2.5 py-1 ring-1 ring-amber-400/30">
                    {c.badge}
                  </div>
                  <Icon className="h-7 w-7 text-amber-300" />
                  <h3 className="mt-5 font-display text-xl font-semibold text-white">
                    {c.title}
                  </h3>
                  <p className="mt-3 text-sm text-slate-400 leading-relaxed">
                    {c.text}
                  </p>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* Closing CTA */}
      <section className="relative">
        <div className="max-w-5xl mx-auto px-6 lg:px-8 pb-20 md:pb-28">
          <div className="relative overflow-hidden rounded-3xl border border-white/10 bg-gradient-to-br from-slate-900 via-slate-950 to-slate-900 p-10 md:p-14 text-center">
            <div className="absolute inset-0 pointer-events-none">
              <div className="absolute -top-24 left-1/2 -translate-x-1/2 h-64 w-[600px] rounded-full bg-emerald-400/10 blur-3xl" />
            </div>
            <div className="relative">
              <h2 className="font-display font-bold text-3xl md:text-5xl tracking-tight text-balance">
                Five days. One engineer. Zero drama.
              </h2>
              <p className="mt-4 text-slate-400 text-lg max-w-xl mx-auto text-pretty">
                Start the clock — we'll have your first reconciled day closed before next Monday.
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
