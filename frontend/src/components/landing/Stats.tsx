import { useEffect, useRef } from "react";
import { countUpOnView } from "@/lib/anime-helpers";

const STATS = [
  { value: 500, suffix: "+", label: "Pumps onboarded" },
  { value: 2, prefix: "₹", suffix: "Cr+", label: "Daily reconciled" },
  { value: 99.9, suffix: "%", label: "Uptime", decimals: 1 },
  { value: 24, suffix: "/7", label: "Support" },
];

export function Stats() {
  const refs = useRef<(HTMLSpanElement | null)[]>([]);

  useEffect(() => {
    const observers = refs.current.map((el, i) => {
      if (!el) return null;
      const s = STATS[i];
      return countUpOnView(el, s.value, {
        prefix: s.prefix ?? "",
        suffix: s.suffix ?? "",
        decimals: s.decimals ?? 0,
      });
    });
    return () => observers.forEach((o) => o?.disconnect());
  }, []);

  return (
    <section className="relative bg-slate-900/40 border-y border-white/5">
      <div className="max-w-7xl mx-auto px-6 lg:px-8 py-20 md:py-24">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-10 md:gap-6">
          {STATS.map((s, i) => (
            <div key={s.label} className="text-center md:text-left">
              <span
                ref={(el) => { refs.current[i] = el; }}
                className="block font-mono font-bold text-4xl md:text-5xl text-white tabular-nums"
              >
                {s.prefix ?? ""}0{s.suffix ?? ""}
              </span>
              <span className="mt-3 block text-slate-500 text-xs uppercase tracking-[0.2em]">
                {s.label}
              </span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
