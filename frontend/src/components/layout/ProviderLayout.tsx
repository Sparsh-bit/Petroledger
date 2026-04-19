import { useEffect, useState } from "react";
import {
  LayoutDashboard,
  Building2,
  CreditCard,
  Inbox,
  Settings,
  Users,
} from "lucide-react";
import { PortalLayout } from "./PortalLayout";
import { accessRequestsApi } from "../../api/access-requests";

export function ProviderLayout() {
  const [newCount, setNewCount] = useState(0);

  useEffect(() => {
    let cancel = false;
    async function load() {
      try {
        const s = await accessRequestsApi.stats();
        if (!cancel) setNewCount(s.new);
      } catch {
        /* badge is best-effort */
      }
    }
    load();
    const t = setInterval(load, 30_000);
    return () => {
      cancel = true;
      clearInterval(t);
    };
  }, []);

  return (
    <PortalLayout
      title="Provider Portal"
      theme="provider"
      nav={[
        {
          to: "/provider/dashboard",
          label: "Dashboard",
          icon: LayoutDashboard,
        },
        { to: "/provider/tenants", label: "Tenants", icon: Building2 },
        {
          to: "/provider/subscriptions",
          label: "Subscriptions",
          icon: CreditCard,
        },
        { to: "/provider/users", label: "Users", icon: Users },
        {
          to: "/provider/access-requests",
          label: "Access Requests",
          icon: Inbox,
          badge: newCount,
        },
        { to: "/provider/settings", label: "Settings", icon: Settings },
      ]}
    />
  );
}
