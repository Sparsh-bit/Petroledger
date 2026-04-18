import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";

export function CTABanner() {
  return (
    <section
      id="cta"
      className="relative bg-gradient-to-br from-amber-500/10 via-slate-950 to-emerald-500/10 border-y border-white/5"
    >
      <div className="max-w-4xl mx-auto px-6 lg:px-8 py-20 md:py-32 text-center">
        <h2 className="font-display font-bold text-4xl md:text-6xl tracking-tighter leading-[1.05] text-balance">
          Get started in minutes.
        </h2>
        <p className="mt-6 text-slate-400 text-lg max-w-xl mx-auto leading-relaxed">
          Spin up your first pump on PetroLedger — no card, no setup call, no spreadsheet imports.
        </p>
        <Link
          to="/login"
          className="mt-10 inline-flex items-center gap-2 h-12 px-8 rounded-full bg-amber-400 text-slate-950 font-medium hover:bg-amber-300 transition-all duration-200 shadow-glow-amber"
        >
          Launch your dashboard
          <ArrowRight className="h-4 w-4" />
        </Link>
      </div>
    </section>
  );
}
