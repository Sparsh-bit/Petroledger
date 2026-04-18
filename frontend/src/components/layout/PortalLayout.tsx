import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { LogOut, Menu } from "lucide-react";
import { useAuth } from "../../store/auth";
import { logoutRequest } from "../../api/auth";
import { useState } from "react";
import { OrgSelector } from "./OrgSelector";

export interface NavItem {
  to: string;
  label: string;
  icon?: React.ComponentType<{ className?: string }>;
}

export function PortalLayout({
  title,
  nav,
}: {
  title: string;
  nav: NavItem[];
}) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);

  async function handleLogout() {
    await logoutRequest();
    logout();
    navigate("/login", { replace: true });
  }

  return (
    <div className="min-h-screen bg-ink-950 text-ink-100">
      <div className="flex min-h-screen">
        <aside
          className={`${
            open ? "block" : "hidden"
          } md:block fixed md:static z-30 inset-y-0 left-0 w-64 border-r border-ink-800 bg-ink-900/70 backdrop-blur-sm`}
        >
          <div className="px-6 py-5 border-b border-ink-800">
            <div className="text-lg font-bold tracking-tight">
              Petro<span className="text-brand-400">Ledger</span>
            </div>
            <div className="text-[11px] uppercase tracking-wider text-ink-500 mt-0.5">
              {title}
            </div>
          </div>
          <nav className="p-3 space-y-1">
            {nav.map((item) => {
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end
                  className={({ isActive }) =>
                    `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition ${
                      isActive
                        ? "bg-brand-500/10 text-brand-300"
                        : "text-ink-300 hover:bg-ink-800/60"
                    }`
                  }
                >
                  {Icon && <Icon className="h-4 w-4" />}
                  {item.label}
                </NavLink>
              );
            })}
          </nav>
        </aside>

        <div className="flex-1 flex flex-col min-w-0">
          <header className="sticky top-0 z-20 flex items-center justify-between border-b border-ink-800 bg-ink-950/80 px-5 py-3 backdrop-blur">
            <button
              className="md:hidden text-ink-300"
              onClick={() => setOpen(!open)}
              aria-label="Toggle navigation"
            >
              <Menu className="h-5 w-5" />
            </button>
            <div className="flex items-center gap-4">
              {(user?.role === "owner" || user?.role === "admin") && (
                <OrgSelector />
              )}
              <div className="text-sm text-ink-400">
                Signed in as{" "}
                <span className="text-ink-100 font-medium">{user?.email}</span>
                <span className="ml-2 rounded-full border border-ink-700 px-2 py-0.5 text-[10px] uppercase tracking-wider">
                  {user?.role}
                </span>
              </div>
            </div>
            <button
              onClick={handleLogout}
              className="inline-flex items-center gap-2 text-sm text-ink-300 hover:text-ink-50"
            >
              <LogOut className="h-4 w-4" /> Logout
            </button>
          </header>
          <main className="flex-1 p-6 md:p-8">
            <Outlet />
          </main>
        </div>
      </div>
    </div>
  );
}
