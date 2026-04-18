import { LayoutDashboard, Building2, CreditCard, Settings } from "lucide-react";
import { PortalLayout } from "./PortalLayout";

export function ProviderLayout() {
  return (
    <PortalLayout
      title="Provider Portal"
      nav={[
        { to: "/provider/dashboard", label: "Dashboard", icon: LayoutDashboard },
        { to: "/provider/organizations", label: "Organizations", icon: Building2 },
        { to: "/provider/subscriptions", label: "Subscriptions", icon: CreditCard },
        { to: "/provider/settings", label: "Settings", icon: Settings },
      ]}
    />
  );
}
