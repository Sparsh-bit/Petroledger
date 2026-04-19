import { Clock, History, LayoutDashboard } from "lucide-react";
import { PortalLayout } from "./PortalLayout";

export function WorkerLayout() {
  return (
    <PortalLayout
      title="Worker Portal"
      theme="worker"
      nav={[
        {
          to: "/worker/dashboard",
          label: "Dashboard",
          icon: LayoutDashboard,
        },
        { to: "/worker/shift", label: "My Shift", icon: Clock },
        { to: "/worker/history", label: "History", icon: History },
      ]}
    />
  );
}
