import {
  BrowserRouter,
  Navigate,
  Route,
  Routes,
  useLocation,
} from "react-router-dom";
import { ReactNode } from "react";
import { LayoutDashboard } from "lucide-react";

import { roleHomePath, useAuth, UserRole } from "../store/auth";
import { PortalLayout } from "../components/layout/PortalLayout";
import { ProviderLayout } from "../components/layout/ProviderLayout";

import LandingPage from "../pages/landing/LandingPage";
import LoginPage from "../pages/auth/LoginPage";
import ForgotPasswordPage from "../pages/auth/ForgotPasswordPage";
import ResetPasswordPage from "../pages/auth/ResetPasswordPage";
import AdminDashboardPage from "../pages/admin/DashboardPage";
import ManagerDashboardPage from "../pages/manager/DashboardPage";
import WorkerDashboardPage from "../pages/worker/DashboardPage";
import ProviderDashboardPage from "../pages/provider/DashboardPage";
import ProviderLoginPage from "../pages/provider/ProviderLoginPage";
import OrganizationsPage from "../pages/provider/OrganizationsPage";
import OrganizationDetailPage from "../pages/provider/OrganizationDetailPage";
import SubscriptionsPage from "../pages/provider/SubscriptionsPage";
import ProviderSettingsPage from "../pages/provider/SettingsPage";
import ProviderUsersPage from "../pages/provider/UsersPage";
import AccessRequestsPage from "../pages/provider/AccessRequestsPage";
import AccessRequestDetailPage from "../pages/provider/AccessRequestDetailPage";
import AboutPage from "../pages/marketing/AboutPage";
import ContactPage from "../pages/marketing/ContactPage";
import RequestAccessPage from "../pages/marketing/RequestAccessPage";
import PrivacyPage from "../pages/marketing/PrivacyPage";
import TermsPage from "../pages/marketing/TermsPage";
import NotFoundPage from "../pages/NotFoundPage";

function ProtectedRoute({
  allowed,
  children,
}: {
  allowed: UserRole[];
  children: ReactNode;
}) {
  const { user, accessToken } = useAuth();
  const location = useLocation();
  if (!accessToken || !user) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }
  if (!allowed.includes(user.role)) {
    return <Navigate to={roleHomePath(user.role)} replace />;
  }
  return <>{children}</>;
}

export function AppRouter() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/forgot-password" element={<ForgotPasswordPage />} />
        <Route path="/reset-password" element={<ResetPasswordPage />} />
        <Route path="/about" element={<AboutPage />} />
        <Route path="/contact" element={<ContactPage />} />
        <Route path="/request-access" element={<RequestAccessPage />} />
        <Route path="/privacy" element={<PrivacyPage />} />
        <Route path="/terms" element={<TermsPage />} />
        <Route path="/provider" element={<ProviderLoginPage />} />

        <Route
          element={
            <ProtectedRoute allowed={["owner", "admin"]}>
              <PortalLayout
                title="Admin Portal"
                nav={[{ to: "/admin/dashboard", label: "Dashboard", icon: LayoutDashboard }]}
              />
            </ProtectedRoute>
          }
        >
          <Route path="/admin/dashboard" element={<AdminDashboardPage />} />
        </Route>

        <Route
          element={
            <ProtectedRoute allowed={["manager"]}>
              <PortalLayout
                title="Manager Portal"
                nav={[{ to: "/manager/dashboard", label: "Dashboard", icon: LayoutDashboard }]}
              />
            </ProtectedRoute>
          }
        >
          <Route path="/manager/dashboard" element={<ManagerDashboardPage />} />
        </Route>

        <Route
          element={
            <ProtectedRoute allowed={["worker"]}>
              <PortalLayout
                title="Worker Portal"
                nav={[{ to: "/worker/dashboard", label: "Dashboard", icon: LayoutDashboard }]}
              />
            </ProtectedRoute>
          }
        >
          <Route path="/worker/dashboard" element={<WorkerDashboardPage />} />
        </Route>

        <Route
          element={
            <ProtectedRoute allowed={["superadmin", "provider"]}>
              <ProviderLayout />
            </ProtectedRoute>
          }
        >
          <Route path="/provider/dashboard" element={<ProviderDashboardPage />} />
          <Route path="/provider/organizations" element={<OrganizationsPage />} />
          <Route
            path="/provider/organizations/:id"
            element={<OrganizationDetailPage />}
          />
          <Route
            path="/provider/subscriptions"
            element={<SubscriptionsPage />}
          />
          <Route path="/provider/users" element={<ProviderUsersPage />} />
          <Route
            path="/provider/access-requests"
            element={<AccessRequestsPage />}
          />
          <Route
            path="/provider/access-requests/:id"
            element={<AccessRequestDetailPage />}
          />
          <Route path="/provider/settings" element={<ProviderSettingsPage />} />
        </Route>

        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </BrowserRouter>
  );
}
