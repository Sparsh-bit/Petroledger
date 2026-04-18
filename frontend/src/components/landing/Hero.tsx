import { useEffect, useRef } from "react";
import { Link } from "react-router-dom";
import { Play, ArrowRight } from "lucide-react";
import { DotPattern } from "@/components/lightswind/dot-pattern";
import { fadeUp, wordReveal, driftBackground } from "@/lib/anime-helpers";
import { cn } from "@/lib/utils";

const HEADLINE = ["Petrol", "pump", "operations,", "finally", "on"];

export function Hero() {
  const eyebrowRef = useRef<HTMLDivElement>(null);
  const wordsRef = useRef<HTMLDivElement>(null);
  const subRef = useRef<HTMLParagraphElement>(null);
  const ctasRef = useRef<HTMLDivElement>(null);
  const dotsRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const tl = (window as any).requestAnimationFrame(() => {
      if (eyebrowRef.current) fadeUp(eyebrowRef.current, { duration: 700 });
      if (wordsRef.current)
        wordReveal(wordsRef.current.querySelectorAll(".hw"), { delay: 250, stagger: 70 });
      if (subRef.current) fadeUp(subRef.current, { delay: 900, duration: 700 });
      if (ctasRef.current)
        fadeUp(ctasRef.current.querySelectorAll(".hcta"), { delay: 1100, stagger: 100 });
    });
    if (dotsRef.current) driftBackground(dotsRef.current);
    return () => cancelAnimationFrame(tl as unknown as number);
  }, []);

  return (
    <section className="relative isolate min-h-screen flex items-center justify-center overflow-hidden pt-24 pb-20">
      <div className="absolute inset-0 hero-radial pointer-events-none" aria-hidden />
      <div ref={dotsRef} className="absolute inset-0 opacity-40 pointer-events-none">
        <DotPattern
          width={28}
          height={28}
          cx={1}
          cy={1}
          cr={1}
          className={cn("[mask-image:radial-gradient(ellipse_at_center,white,transparent_75%)] fill-slate-500/40")}
        />
      </div>

      <div className="relative max-w-6xl mx-auto px-6 lg:px-8 text-center">
        <div ref={eyebrowRef} style={{ opacity: 0 }} className="inline-flex items-center gap-2 rounded-full bg-white/5 border border-white/10 px-3 py-1 text-xs text-slate-300">
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
          Trusted by 500+ petrol pumps across India
        </div>

        <h1
          ref={wordsRef}
          className="mt-7 font-display font-bold tracking-tighter leading-[0.95] text-balance text-5xl sm:text-6xl md:text-7xl lg:text-8xl"
        >
          {HEADLINE.map((w, i) => (
            <span key={i} className="hw inline-block mr-[0.25em]" style={{ opacity: 0 }}>
              {w}
            </span>
          ))}
          <span
            className="hw inline-block bg-gradient-to-r from-amber-400 via-amber-300 to-emerald-400 bg-clip-text text-transparent"
            style={{ opacity: 0 }}
          >
            autopilot.
          </span>
        </h1>

        <p
          ref={subRef}
          style={{ opacity: 0 }}
          className="mt-7 max-w-2xl mx-auto text-lg md:text-xl text-slate-400 leading-relaxed font-medium text-pretty"
        >
          Daily reconciliation, fleet card ingestion, role-based access, and live dashboards —
          built for owners who treat their pump like a real business.
        </p>

        <div ref={ctasRef} className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-3">
          <Link
            to="/login"
            className="hcta group inline-flex items-center gap-2 h-12 px-7 rounded-full bg-amber-400 text-slate-950 font-medium hover:bg-amber-300 transition-all duration-200 shadow-glow-amber"
            style={{ opacity: 0 }}
          >
            Start free trial
            <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
          </Link>
          <a
            href="#features"
            className="hcta inline-flex items-center gap-2 h-12 px-7 rounded-full border border-white/10 bg-white/[0.03] text-slate-200 font-medium hover:bg-white/[0.06] hover:border-white/20 transition-all duration-200"
            style={{ opacity: 0 }}
          >
            <Play className="h-4 w-4 text-amber-400" />
            Watch demo
          </a>
        </div>

        <div className="mt-16 flex flex-col items-center gap-4">
          <span className="text-xs uppercase tracking-[0.2em] text-slate-500">Trusted by</span>
          <div className="flex flex-wrap items-center justify-center gap-8 grayscale opacity-60">
            {["HPCL", "BPCL", "IOCL", "Reliance", "Nayara"].map((n) => (
              <span key={n} className="font-display font-semibold text-slate-400 text-lg">
                {n}
              </span>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
