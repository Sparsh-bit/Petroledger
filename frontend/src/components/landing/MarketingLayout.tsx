import { ReactNode } from "react";
import { Nav } from "./Nav";
import { Footer } from "./Footer";

interface MarketingLayoutProps {
  children: ReactNode;
  /**
   * When true, removes the default narrow content container so the page
   * can provide its own full-width sections (hero bands, feature grids, etc).
   */
  wide?: boolean;
}

export function MarketingLayout({ children, wide = false }: MarketingLayoutProps) {
  return (
    <main className="min-h-screen bg-slate-950 text-slate-100 selection:bg-amber-400/30 selection:text-white">
      <Nav />
      {wide ? (
        <div className="pt-16">{children}</div>
      ) : (
        <div className="pt-24 pb-20 px-6 lg:px-8 max-w-4xl mx-auto">
          {children}
        </div>
      )}
      <Footer />
    </main>
  );
}
