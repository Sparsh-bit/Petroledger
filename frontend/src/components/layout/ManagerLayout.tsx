import {
  Activity,
  FileText,
  LayoutDashboard,
  RefreshCw,
} from "lucide-react";
import { PortalLayout } from "./PortalLayout";

export function ManagerLayout() {
  return (
    <PortalLayout
      title="Manager Portal"
      theme="manager"
      nav={[
        {
          to: "/manager/dashboard",
          label: "Dashboard",
          icon: LayoutDashboard,
        },
        { to: "/manager/shifts", label: "Shifts", icon: Activity },
        {
          to: "/manager/reconciliation",
          label: "Reconciliation",
          icon: RefreshCw,
        },
        { to: "/manager/reports", label: "Reports", icon: FileText },
      ]}
    />
  );
}
