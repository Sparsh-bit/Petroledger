import { useEffect, useRef } from "react";
import {
  BarChart3,
  Users,
  Truck,
  AlertTriangle,
  Activity,
  FileSearch,
} from "lucide-react";
import { fadeUpOnView } from "@/lib/anime-helpers";

const FEATURES = [
  {
    icon: BarChart3,
    title: "Daily Reconciliation",
    text: "Match nozzle sales, POS batches, UPI and cash automatically — every single day.",
  },
  {
    icon: Users,
    title: "Multi-Role Access",
    text: "Owner, Admin, Manager and Worker portals with the right permissions for each role.",
  },
  {
    icon: Truck,
    title: "FMS Integration",
    text: "Ingest HPCL, BPCL and IOCL fleet-card feeds without touching a single spreadsheet.",
  },
  {
    icon: AlertTriangle,
    title: "Variance Alerts",
    text: "Spot density drift, density loss and short-deliveries the minute they happen.",
  },
  {
    icon: Activity,
    title: "Live Dashboards",
    text: "Sales, dips, shifts and credit — all on one screen, refreshed in real time.",
  },
  {
    icon: FileSearch,
    title: "Audit-Ready Books",
    text: "Every entry is timestamped, signed, and exportable to your auditor in one click.",
  },
];

export function Features() {
  const gridRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (gridRef.current) {
      fadeUpOnView(gridRef.current, ".feat-card", { stagger: 80 });
    }
  }, []);

  return (
    <section id="features" className="relative">
      <div className="max-w-7xl mx-auto px-6 lg:px-8 py-20 md:py-32">
        <div className="max-w-3xl">
          <span className="text-xs font-mono uppercase tracking-[0.2em] text-amber-400/80">
            Features
          </span>
          <h2 className="mt-4 font-display font-bold text-4xl md:text-5xl tracking-tight text-balance">
            Everything you need to run a modern fuel station.
          </h2>
          <p className="mt-5 text-slate-400 text-lg leading-relaxed text-pretty">
            One platform that connects your nozzles, your team, and your books — so closing the day
            takes minutes, not hours.
          </p>
        </div>

        <div ref={gridRef} className="mt-16 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {FEATURES.map((f) => {
            const Icon = f.icon;
            return (
              <div
                key={f.title}
                className="feat-card group rounded-2xl border border-white/5 bg-white/[0.02] hover:bg-white/[0.04] hover:border-white/10 p-8 transition-all duration-300"
              >
                <div className="inline-flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br from-amber-400/20 to-emerald-400/20 ring-1 ring-white/10">
                  <Icon className="h-5 w-5 text-amber-300" />
                </div>
                <h3 className="mt-6 font-display text-xl font-semibold text-white">{f.title}</h3>
                <p className="mt-2 text-slate-400 text-sm leading-relaxed">{f.text}</p>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
