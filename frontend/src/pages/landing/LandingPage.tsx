import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import {
  Activity,
  BarChart3,
  FileCheck2,
  Fuel,
  Gauge,
  ShieldCheck,
  Users,
  ArrowRight,
} from "lucide-react";

const FEATURES = [
  {
    icon: FileCheck2,
    title: "Daily Reconciliation",
    text: "Match nozzle sales, POS batches, UPI and cash — every single day, automatically.",
  },
  {
    icon: Users,
    title: "Multi-Role Access",
    text: "Owner, Admin, Manager and Worker portals — each with the right permissions.",
  },
  {
    icon: Fuel,
    title: "FMS Integration",
    text: "Ingest HPCL, BPCL and IOCL fleet-card feeds without a single spreadsheet.",
  },
  {
    icon: ShieldCheck,
    title: "Anomaly Detection",
    text: "ML-powered flags on variance, density and meter drift before they become losses.",
  },
  {
    icon: BarChart3,
    title: "Real-time Analytics",
    text: "Live KPIs on throughput, shift performance and margin — on every device.",
  },
  {
    icon: Activity,
    title: "Immutable Audit Trail",
    text: "Every edit, approval and override is stamped, hashed and queryable.",
  },
];

const STEPS = [
  {
    n: "01",
    title: "Connect your pumps",
    text: "Onboard in a day — we import your nozzles, shifts and bank accounts.",
  },
  {
    n: "02",
    title: "Capture shift data",
    text: "Workers log readings on mobile; managers approve in one tap.",
  },
  {
    n: "03",
    title: "Reconcile & report",
    text: "Variance reports and GST-ready exports, waiting for you every morning.",
  },
];

const PRICING = [
  {
    tier: "Basic",
    price: "₹1,999",
    tag: "per pump / month",
    features: ["1 pump", "Up to 5 users", "Email support", "Daily reconciliation"],
    cta: "Start free trial",
    accent: false,
  },
  {
    tier: "Pro",
    price: "₹4,999",
    tag: "per pump / month",
    features: [
      "Up to 5 pumps",
      "Unlimited users",
      "FMS integrations",
      "Anomaly detection",
      "Priority support",
    ],
    cta: "Start free trial",
    accent: true,
  },
  {
    tier: "Enterprise",
    price: "Let's talk",
    tag: "custom pricing",
    features: [
      "Unlimited pumps",
      "Dedicated success manager",
      "Custom integrations",
      "SLA & on-prem options",
    ],
    cta: "Contact sales",
    accent: false,
  },
];

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-ink-950 text-ink-100 overflow-x-hidden">
      <NavBar />

      {/* HERO */}
      <section className="relative">
        <div className="absolute inset-0 grid-bg opacity-40 pointer-events-none" />
        <div className="absolute inset-0 hero-radial pointer-events-none" />
        <div className="relative max-w-7xl mx-auto px-6 pt-24 pb-28 lg:pt-36 lg:pb-40">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7 }}
            className="max-w-3xl"
          >
            <div className="inline-flex items-center gap-2 rounded-full border border-brand-500/30 bg-brand-500/10 px-3 py-1 text-xs text-brand-300">
              <span className="h-1.5 w-1.5 rounded-full bg-brand-400 animate-pulse" />
              Now open for early access in India
            </div>
            <h1 className="mt-6 text-5xl sm:text-6xl lg:text-7xl font-bold tracking-tight leading-[1.05]">
              Petrol Pump Management,{" "}
              <span className="bg-gradient-to-r from-brand-400 via-brand-300 to-emerald-200 bg-clip-text text-transparent">
                Reimagined.
              </span>
            </h1>
            <p className="mt-6 text-lg sm:text-xl text-ink-300 max-w-2xl">
              PetroLedger is the unified platform for reconciliation, FMS,
              staff and analytics — engineered for Indian dealers who are
              tired of spreadsheets and Sunday-night surprises.
            </p>
            <div className="mt-10 flex flex-wrap gap-4">
              <Link
                to="/login"
                className="group inline-flex items-center gap-2 rounded-lg bg-brand-500 px-6 py-3.5 text-sm font-semibold text-ink-950 shadow-glow hover:bg-brand-400 transition"
              >
                Get Started
                <ArrowRight className="h-4 w-4 transition group-hover:translate-x-0.5" />
              </Link>
              <Link
                to="/login"
                className="inline-flex items-center gap-2 rounded-lg border border-ink-700 bg-ink-900/60 px-6 py-3.5 text-sm font-semibold text-ink-100 hover:bg-ink-800 transition"
              >
                Sign In
              </Link>
            </div>
          </motion.div>
        </div>
      </section>

      {/* STATS */}
      <section className="border-y border-ink-800 bg-ink-900/40">
        <div className="max-w-7xl mx-auto px-6 py-10 grid grid-cols-1 sm:grid-cols-3 gap-6 text-center">
          {[
            ["500+", "pumps onboarded"],
            ["₹2 Cr+", "daily reconciled"],
            ["99.9%", "uptime"],
          ].map(([big, small]) => (
            <div key={big}>
              <div className="text-3xl sm:text-4xl font-bold text-ink-50">
                {big}
              </div>
              <div className="mt-1 text-sm uppercase tracking-wider text-ink-400">
                {small}
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* FEATURES */}
      <section id="features" className="max-w-7xl mx-auto px-6 py-24">
        <div className="max-w-2xl">
          <div className="text-xs uppercase tracking-[0.2em] text-brand-400">
            Platform
          </div>
          <h2 className="mt-3 text-3xl sm:text-4xl font-bold">
            Everything your forecourt needs, under one dashboard.
          </h2>
          <p className="mt-4 text-ink-400">
            Built with the same rigour your auditors expect — and the mobile
            speed your forecourt staff actually use.
          </p>
        </div>
        <div className="mt-12 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {FEATURES.map((f, i) => (
            <motion.div
              key={f.title}
              initial={{ opacity: 0, y: 14 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.4, delay: i * 0.05 }}
              className="rounded-2xl border border-ink-800 bg-ink-900/40 p-6 hover:border-brand-500/40 transition"
            >
              <div className="inline-flex h-10 w-10 items-center justify-center rounded-lg bg-brand-500/15 text-brand-300">
                <f.icon className="h-5 w-5" />
              </div>
              <div className="mt-4 font-semibold">{f.title}</div>
              <div className="mt-1.5 text-sm text-ink-400">{f.text}</div>
            </motion.div>
          ))}
        </div>
      </section>

      {/* HOW IT WORKS */}
      <section className="bg-ink-900/40 border-y border-ink-800">
        <div className="max-w-7xl mx-auto px-6 py-24">
          <div className="text-xs uppercase tracking-[0.2em] text-brand-400">
            How it works
          </div>
          <h2 className="mt-3 text-3xl sm:text-4xl font-bold">
            From chaos to closing in three steps.
          </h2>
          <div className="mt-12 grid grid-cols-1 md:grid-cols-3 gap-6">
            {STEPS.map((s) => (
              <div
                key={s.n}
                className="rounded-2xl border border-ink-800 bg-ink-950/50 p-7"
              >
                <div className="text-5xl font-bold text-brand-400/30">
                  {s.n}
                </div>
                <div className="mt-4 text-lg font-semibold">{s.title}</div>
                <p className="mt-2 text-sm text-ink-400">{s.text}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* PRICING */}
      <section id="pricing" className="max-w-7xl mx-auto px-6 py-24">
        <div className="max-w-2xl">
          <div className="text-xs uppercase tracking-[0.2em] text-brand-400">
            Pricing
          </div>
          <h2 className="mt-3 text-3xl sm:text-4xl font-bold">
            Honest pricing. No pump left behind.
          </h2>
        </div>
        <div className="mt-12 grid grid-cols-1 md:grid-cols-3 gap-5">
          {PRICING.map((p) => (
            <div
              key={p.tier}
              className={`relative rounded-2xl border p-7 ${
                p.accent
                  ? "border-brand-500/50 bg-gradient-to-b from-brand-500/10 to-transparent shadow-glow"
                  : "border-ink-800 bg-ink-900/40"
              }`}
            >
              {p.accent && (
                <div className="absolute -top-3 left-7 rounded-full bg-brand-500 px-3 py-1 text-[10px] font-bold uppercase tracking-wider text-ink-950">
                  Most popular
                </div>
              )}
              <div className="text-sm uppercase tracking-wider text-ink-400">
                {p.tier}
              </div>
              <div className="mt-3 flex items-baseline gap-2">
                <div className="text-4xl font-bold">{p.price}</div>
                <div className="text-sm text-ink-500">{p.tag}</div>
              </div>
              <ul className="mt-6 space-y-2 text-sm text-ink-300">
                {p.features.map((f) => (
                  <li key={f} className="flex items-start gap-2">
                    <Gauge className="mt-0.5 h-4 w-4 text-brand-400 shrink-0" />
                    {f}
                  </li>
                ))}
              </ul>
              <Link
                to="/login"
                className={`mt-7 inline-flex w-full items-center justify-center rounded-lg px-4 py-2.5 text-sm font-semibold transition ${
                  p.accent
                    ? "bg-brand-500 text-ink-950 hover:bg-brand-400"
                    : "border border-ink-700 hover:bg-ink-800"
                }`}
              >
                {p.cta}
              </Link>
            </div>
          ))}
        </div>
      </section>

      <Footer />
    </div>
  );
}

function NavBar() {
  return (
    <header className="sticky top-0 z-40 backdrop-blur-md bg-ink-950/60 border-b border-ink-900">
      <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
        <Link to="/" className="flex items-center gap-2 font-bold text-lg">
          <span className="inline-flex h-8 w-8 items-center justify-center rounded-lg bg-brand-500/20 text-brand-300">
            <Fuel className="h-4 w-4" />
          </span>
          Petro<span className="text-brand-400">Ledger</span>
        </Link>
        <nav className="hidden md:flex items-center gap-8 text-sm text-ink-300">
          <a href="#features" className="hover:text-ink-50">
            Features
          </a>
          <a href="#pricing" className="hover:text-ink-50">
            Pricing
          </a>
          <a href="#contact" className="hover:text-ink-50">
            Contact
          </a>
        </nav>
        <Link
          to="/login"
          className="rounded-lg bg-brand-500 px-4 py-2 text-sm font-semibold text-ink-950 hover:bg-brand-400 transition"
        >
          Login
        </Link>
      </div>
    </header>
  );
}

function Footer() {
  return (
    <footer id="contact" className="border-t border-ink-800 bg-ink-950">
      <div className="max-w-7xl mx-auto px-6 py-14 grid grid-cols-2 md:grid-cols-4 gap-8 text-sm">
        <div className="col-span-2">
          <div className="flex items-center gap-2 font-bold">
            <Fuel className="h-4 w-4 text-brand-400" /> PetroLedger
          </div>
          <p className="mt-3 text-ink-400 max-w-xs">
            The operating system for modern petrol-pump dealers across India.
          </p>
        </div>
        <div>
          <div className="text-ink-500 uppercase text-xs tracking-wider">
            Product
          </div>
          <ul className="mt-3 space-y-2 text-ink-300">
            <li>
              <a href="#features">Features</a>
            </li>
            <li>
              <a href="#pricing">Pricing</a>
            </li>
            <li>
              <Link to="/login">Login</Link>
            </li>
          </ul>
        </div>
        <div>
          <div className="text-ink-500 uppercase text-xs tracking-wider">
            Company
          </div>
          <ul className="mt-3 space-y-2 text-ink-300">
            <li>About</li>
            <li>Careers</li>
            <li>Contact</li>
          </ul>
        </div>
      </div>
      <div className="border-t border-ink-900 py-6 text-center text-xs text-ink-500">
        © {new Date().getFullYear()} PetroLedger. All rights reserved.
      </div>
    </footer>
  );
}
