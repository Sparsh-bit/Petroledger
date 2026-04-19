import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { ChevronRight, LogOut, Menu, Shield, X } from "lucide-react";
import { useAuth } from "../../store/auth";
import { logoutRequest } from "../../api/auth";
import { useState } from "react";
import { OrgSelector } from "./OrgSelector";

export interface NavItem {
  to: string;
  label: string;
  icon?: React.ComponentType<{ className?: string }>;
  badge?: number;
}

export type PortalTheme = "provider" | "admin" | "manager" | "worker";

// Per-portal accents are kept subtle so the surfaces remain cohesive —
// only the brand wordmark hue differs; sidebar chrome is always light.
const THEME_BRAND: Record<PortalTheme, { brand: string; pill: string }> = {
  provider: { brand: "text-indigo-600", pill: "text-indigo-600" },
  admin: { brand: "text-emerald-600", pill: "text-emerald-600" },
  manager: { brand: "text-sky-600", pill: "text-sky-600" },
  worker: { brand: "text-amber-600", pill: "text-amber-600" },
};

const PORTAL_LABEL: Record<PortalTheme, string> = {
  provider: "Provider Portal",
  admin: "Admin Portal",
  manager: "Manager Portal",
  worker: "Worker Portal",
};

export interface PortalLayoutProps {
  title: string;
  nav: NavItem[];
  theme?: PortalTheme;
}

export function PortalLayout({
  title,
  nav,
  theme = "admin",
}: PortalLayoutProps) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const brand = THEME_BRAND[theme];

  async function handleLogout() {
    await logoutRequest();
    logout();
    navigate("/login", { replace: true });
  }

  function closeMobile() {
    setOpen(false);
  }

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <div className="flex min-h-screen">
        {open && (
          <button
            type="button"
            aria-label="Close navigation"
            onClick={closeMobile}
            className="fixed inset-0 z-20 bg-slate-900/30 md:hidden"
          />
        )}

        <aside
          className={`${open ? "translate-x-0" : "-translate-x-full"} md:translate-x-0 fixed md:static z-30 inset-y-0 left-0 w-64 flex flex-col border-r border-slate-100 bg-white transition-transform duration-200`}
        >
          <div className="px-6 py-5 flex items-center justify-between border-b border-slate-100">
            <div className="flex items-center gap-2.5">
              <span className="inline-flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-600 to-purple-600 text-white shadow-sm">
                <Shield className="h-4 w-4" />
              </span>
              <div>
                <div className="text-sm font-bold tracking-tight text-slate-900">
                  Petro<span className={brand.brand}>Ledger</span>
                </div>
                <div className="text-[10px] uppercase tracking-widest text-slate-400 mt-0.5">
                  {PORTAL_LABEL[theme] || title}
                </div>
              </div>
            </div>
            <button
              type="button"
              className="md:hidden text-slate-500 hover:text-slate-900"
              onClick={closeMobile}
              aria-label="Close navigation"
            >
              <X className="h-5 w-5" />
            </button>
          </div>

          <nav className="flex-1 overflow-y-auto p-4 space-y-1">
            {nav.map((item) => {
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end
                  onClick={closeMobile}
                  className={({ isActive }) =>
                    `group flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition ${
                      isActive
                        ? "bg-indigo-600 text-white shadow-md shadow-indigo-200"
                        : "text-slate-600 hover:text-slate-900 hover:bg-slate-50"
                    }`
                  }
                >
                  {({ isActive }) => (
                    <>
                      {Icon && <Icon className="h-4 w-4 shrink-0" />}
                      <span className="flex-1 truncate font-medium">
                        {item.label}
                      </span>
                      {item.badge && item.badge > 0 ? (
                        <span
                          className={`inline-flex items-center justify-center min-w-[1.25rem] h-5 px-1.5 rounded-full text-[10px] font-bold ${
                            isActive
                              ? "bg-white/20 text-white"
                              : "bg-indigo-50 text-indigo-600"
                          }`}
                        >
                          {item.badge > 99 ? "99+" : item.badge}
                        </span>
                      ) : isActive ? (
                        <ChevronRight className="h-4 w-4 text-white/70" />
                      ) : null}
                    </>
                  )}
                </NavLink>
              );
            })}
          </nav>

          <div className="border-t border-slate-100 px-4 py-4">
            <div className="flex items-center gap-3 rounded-xl bg-slate-50 px-3 py-2.5">
              <span
                className={`inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-white text-xs font-bold ${brand.pill}`}
              >
                {user?.email?.charAt(0).toUpperCase() ?? "?"}
              </span>
              <div className="flex-1 min-w-0">
                <div className="truncate text-xs font-semibold text-slate-900">
                  {user?.email ?? "—"}
                </div>
                <div className="text-[10px] uppercase tracking-widest text-slate-400">
                  {user?.role ?? ""}
                </div>
              </div>
            </div>
            <button
              onClick={handleLogout}
              className="mt-3 w-full inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-slate-500 hover:text-rose-600 hover:bg-rose-50 transition"
            >
              <LogOut className="h-4 w-4" /> Sign out
            </button>
          </div>
        </aside>

        <div className="flex-1 flex flex-col min-w-0">
          <header className="sticky top-0 z-10 h-16 flex items-center justify-between border-b border-slate-100 bg-white px-4 md:px-6">
            <div className="flex items-center gap-3">
              <button
                type="button"
                className="md:hidden text-slate-700"
                onClick={() => setOpen(true)}
                aria-label="Open navigation"
              >
                <Menu className="h-5 w-5" />
              </button>
              {(user?.role === "owner" || user?.role === "admin") && (
                <OrgSelector />
              )}
            </div>
            <div className="flex items-center gap-3 text-sm">
              <span className="hidden sm:inline text-slate-500">
                Signed in as{" "}
                <span className="text-slate-900 font-medium">
                  {user?.email}
                </span>
              </span>
              <span className="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-widest text-slate-600">
                {user?.role}
              </span>
              <button
                onClick={handleLogout}
                className="inline-flex items-center gap-2 text-slate-500 hover:text-rose-600 transition"
              >
                <LogOut className="h-4 w-4" />
                <span className="hidden sm:inline">Logout</span>
              </button>
            </div>
          </header>

          <main className="flex-1 p-4 sm:p-6">
            <div className="mx-auto max-w-6xl">
              <Outlet />
            </div>
          </main>
        </div>
      </div>
    </div>
  );
}
