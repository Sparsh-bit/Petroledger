import { ReactNode } from "react";
import { Nav } from "./Nav";
import { Footer } from "./Footer";

export function MarketingLayout({ children }: { children: ReactNode }) {
  return (
    <main className="min-h-screen bg-slate-950 text-slate-100 selection:bg-amber-400/30 selection:text-white">
      <Nav />
      <div className="pt-24 pb-20 px-6 lg:px-8 max-w-4xl mx-auto">
        {children}
      </div>
      <Footer />
    </main>
  );
}
