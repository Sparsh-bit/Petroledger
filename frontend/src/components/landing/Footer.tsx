import { Link } from "react-router-dom";
import { Droplet } from "lucide-react";

interface FooterLink {
  label: string;
  to: string;
  external?: boolean;
}

const COLS: { title: string; links: FooterLink[] }[] = [
  {
    title: "Product",
    links: [
      { label: "Features", to: "/features" },
      { label: "Pricing", to: "/pricing" },
      { label: "How it works", to: "/how-it-works" },
      { label: "Request access", to: "/request-access" },
      { label: "Sign in", to: "/login" },
    ],
  },
  {
    title: "Company",
    links: [
      { label: "About", to: "/about" },
      { label: "Contact", to: "/contact" },
      { label: "Provider portal", to: "/provider" },
    ],
  },
  {
    title: "Legal",
    links: [
      { label: "Privacy", to: "/privacy" },
      { label: "Terms", to: "/terms" },
    ],
  },
];

export function Footer() {
  return (
    <footer className="border-t border-white/5 bg-slate-950">
      <div className="max-w-7xl mx-auto px-6 lg:px-8 py-16">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-10">
          <div className="col-span-2 md:col-span-1">
            <Link to="/" className="flex items-center gap-2 font-display font-bold text-lg">
              <span className="inline-flex h-7 w-7 items-center justify-center rounded-lg bg-amber-400/15 ring-1 ring-amber-400/40">
                <Droplet className="h-4 w-4 text-amber-400" />
              </span>
              Petro<span className="text-amber-400">Ledger</span>
            </Link>
            <p className="mt-4 text-sm text-slate-500 leading-relaxed max-w-xs">
              Petrol pump operations, finally on autopilot. Built in India for India.
            </p>
          </div>

          {COLS.map((c) => (
            <div key={c.title}>
              <h4 className="font-display text-xs uppercase tracking-[0.2em] text-slate-400">
                {c.title}
              </h4>
              <ul className="mt-4 space-y-2">
                {c.links.map((l) => (
                  <li key={l.label}>
                    {l.external ? (
                      <a
                        href={l.to}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-sm text-slate-500 hover:text-white transition-colors"
                      >
                        {l.label}
                      </a>
                    ) : l.to.startsWith("/#") ? (
                      <a
                        href={l.to.slice(1)}
                        className="text-sm text-slate-500 hover:text-white transition-colors"
                      >
                        {l.label}
                      </a>
                    ) : (
                      <Link
                        to={l.to}
                        className="text-sm text-slate-500 hover:text-white transition-colors"
                      >
                        {l.label}
                      </Link>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="mt-12 pt-8 border-t border-white/5 flex flex-col sm:flex-row items-center justify-between gap-4">
          <p className="text-xs text-slate-500 font-mono">
            © {new Date().getFullYear()} PetroLedger. All rights reserved.
          </p>
          <div className="flex flex-wrap items-center gap-4 text-xs text-slate-500">
            <a
              href="mailto:official.concilio@gmail.com"
              className="hover:text-white transition-colors"
            >
              official.concilio@gmail.com
            </a>
            <a
              href="tel:+918840268280"
              className="hover:text-white transition-colors"
            >
              +91 88402 68280
            </a>
            <a
              href="https://concilio.solutions"
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-white transition-colors"
            >
              concilio.solutions
            </a>
          </div>
        </div>
      </div>
    </footer>
  );
}
