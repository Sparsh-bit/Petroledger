import {
  AlertTriangle,
  BarChart3,
  FileText,
  Fuel,
  LayoutDashboard,
  Package,
  RefreshCw,
  ScrollText,
  Users,
  Wrench,
  Activity,
} from "lucide-react";
import { PortalLayout } from "./PortalLayout";

export function ManagerLayout() {
  return (
    <PortalLayout
      title="Manager Portal"
      theme="manager"
      nav={[
        { to: "/manager/dashboard", label: "Dashboard", icon: LayoutDashboard },
        { to: "/manager/pumps", label: "Pumps", icon: Fuel },
        { to: "/manager/workers", label: "Workers", icon: Users },
        { to: "/manager/shifts", label: "Shifts", icon: Activity },
        {
          to: "/manager/reconciliation",
          label: "Reconciliation",
          icon: RefreshCw,
        },
        { to: "/manager/analytics", label: "Analytics", icon: BarChart3 },
        { to: "/manager/inventory", label: "Inventory", icon: Package },
        { to: "/manager/maintenance", label: "Maintenance", icon: Wrench },
        {
          to: "/manager/anomalies",
          label: "Anomalies",
          icon: AlertTriangle,
        },
        { to: "/manager/reports", label: "Reports", icon: FileText },
        { to: "/manager/audit-logs", label: "Audit Logs", icon: ScrollText },
      ]}
    />
  );
}
