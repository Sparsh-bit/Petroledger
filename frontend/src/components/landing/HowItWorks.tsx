import { useEffect, useRef } from "react";
import { fadeUpOnView } from "@/lib/anime-helpers";

const STEPS = [
  {
    n: "01",
    title: "Connect your pumps",
    text: "Link nozzles, POS terminals, and fleet-card feeds in under an hour.",
  },
  {
    n: "02",
    title: "Configure roles",
    text: "Invite owners, managers and workers — each with the permissions they need.",
  },
  {
    n: "03",
    title: "Get daily reports",
    text: "Variance, sales and credit reports land in your inbox every morning.",
  },
];

export function HowItWorks() {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (ref.current) fadeUpOnView(ref.current, ".step", { stagger: 120 });
  }, []);

  return (
    <section id="how" className="relative bg-slate-900/30 border-y border-white/5">
      <div className="max-w-7xl mx-auto px-6 lg:px-8 py-20 md:py-32">
        <div className="max-w-3xl">
          <span className="text-xs font-mono uppercase tracking-[0.2em] text-amber-400/80">
            How it works
          </span>
          <h2 className="mt-4 font-display font-bold text-4xl md:text-5xl tracking-tight text-balance">
            Live in three steps.
          </h2>
        </div>

        <div ref={ref} className="relative mt-16 grid md:grid-cols-3 gap-10 md:gap-6">
          <div className="hidden md:block absolute top-7 left-[16%] right-[16%] h-px bg-gradient-to-r from-transparent via-amber-400/30 to-transparent" />
          {STEPS.map((s) => (
            <div key={s.n} className="step relative text-center md:text-left">
              <div className="inline-flex h-14 w-14 items-center justify-center rounded-full border border-amber-400/40 bg-slate-950 font-mono font-bold text-amber-400 text-lg">
                {s.n}
              </div>
              <h3 className="mt-6 font-display text-xl font-semibold text-white">{s.title}</h3>
              <p className="mt-2 text-slate-400 leading-relaxed text-pretty">{s.text}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
