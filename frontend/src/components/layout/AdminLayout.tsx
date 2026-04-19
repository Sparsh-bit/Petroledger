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

export function AdminLayout() {
  return (
    <PortalLayout
      title="Admin Portal"
      theme="admin"
      nav={[
        { to: "/admin/dashboard", label: "Dashboard", icon: LayoutDashboard },
        { to: "/admin/pumps", label: "Pumps", icon: Fuel },
        { to: "/admin/workers", label: "Workers", icon: Users },
        { to: "/admin/shifts", label: "Shifts", icon: Activity },
        {
          to: "/admin/reconciliation",
          label: "Reconciliation",
          icon: RefreshCw,
        },
        { to: "/admin/analytics", label: "Analytics", icon: BarChart3 },
        { to: "/admin/inventory", label: "Inventory", icon: Package },
        { to: "/admin/maintenance", label: "Maintenance", icon: Wrench },
        {
          to: "/admin/anomalies",
          label: "Anomalies",
          icon: AlertTriangle,
        },
        { to: "/admin/reports", label: "Reports", icon: FileText },
        { to: "/admin/audit-logs", label: "Audit Logs", icon: ScrollText },
      ]}
    />
  );
}
