import { Droplet, Github, Twitter, Linkedin } from "lucide-react";

const COLS = [
  {
    title: "Product",
    links: ["Features", "Pricing", "Integrations", "Changelog"],
  },
  {
    title: "Company",
    links: ["About", "Customers", "Careers", "Contact"],
  },
  {
    title: "Legal",
    links: ["Privacy", "Terms", "Security", "DPA"],
  },
];

export function Footer() {
  return (
    <footer className="border-t border-white/5 bg-slate-950">
      <div className="max-w-7xl mx-auto px-6 lg:px-8 py-16">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-10">
          <div className="col-span-2 md:col-span-1">
            <div className="flex items-center gap-2 font-display font-bold text-lg">
              <span className="inline-flex h-7 w-7 items-center justify-center rounded-lg bg-amber-400/15 ring-1 ring-amber-400/40">
                <Droplet className="h-4 w-4 text-amber-400" />
              </span>
              Petro<span className="text-amber-400">Ledger</span>
            </div>
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
                  <li key={l}>
                    <a href="#" className="text-sm text-slate-500 hover:text-white transition-colors">
                      {l}
                    </a>
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
          <div className="flex items-center gap-4 text-slate-500">
            <a href="#" aria-label="Twitter" className="hover:text-white transition-colors">
              <Twitter className="h-4 w-4" />
            </a>
            <a href="#" aria-label="GitHub" className="hover:text-white transition-colors">
              <Github className="h-4 w-4" />
            </a>
            <a href="#" aria-label="LinkedIn" className="hover:text-white transition-colors">
              <Linkedin className="h-4 w-4" />
            </a>
          </div>
        </div>
      </div>
    </footer>
  );
}
