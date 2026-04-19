import { Link } from "react-router-dom";
import { Droplet } from "lucide-react";

export function Nav() {
  return (
    <header className="fixed top-0 inset-x-0 z-50 backdrop-blur-xl bg-slate-950/70 border-b border-white/5">
      <div className="max-w-7xl mx-auto px-6 lg:px-8 h-16 flex items-center justify-between">
        <Link to="/" className="flex items-center gap-2 font-display font-bold text-lg tracking-tight">
          <span className="inline-flex h-7 w-7 items-center justify-center rounded-lg bg-amber-400/15 ring-1 ring-amber-400/40">
            <Droplet className="h-4 w-4 text-amber-400" />
          </span>
          <span>Petro<span className="text-amber-400">Ledger</span></span>
        </Link>

        <nav className="hidden md:flex items-center gap-8 font-display text-sm font-medium text-slate-300">
          <Link to="/features" className="hover:text-white transition-colors">Features</Link>
          <Link to="/pricing" className="hover:text-white transition-colors">Pricing</Link>
          <Link to="/how-it-works" className="hover:text-white transition-colors">How it works</Link>
          <Link to="/contact" className="hover:text-white transition-colors">Contact</Link>
        </nav>

        <div className="flex items-center gap-2">
          <Link
            to="/login"
            className="hidden sm:inline-flex items-center h-10 px-4 rounded-full text-sm font-medium text-slate-300 hover:text-white hover:bg-white/5 transition-all duration-200"
          >
            Sign in
          </Link>
          <Link
            to="/request-access"
            className="inline-flex items-center h-10 px-5 rounded-full text-sm font-medium bg-amber-400 text-slate-950 hover:bg-amber-300 transition-all duration-200 shadow-glow-amber"
          >
            Request access
          </Link>
        </div>
      </div>
    </header>
  );
}
