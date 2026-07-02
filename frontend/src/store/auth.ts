import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

export type UserRole =
  | "owner"
  | "admin"
  | "manager"
  | "worker"
  | "superadmin"
  | "provider";

export interface AuthUser {
  id: string;
  email: string;
  role: UserRole;
  org_id: string | null;
}

interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  user: AuthUser | null;
  setTokens: (access: string, refresh: string) => void;
  setUser: (user: AuthUser) => void;
  logout: () => void;
  isAuthenticated: () => boolean;
}

export const useAuth = create<AuthState>()(
  persist(
    (set, get) => ({
      accessToken: null,
      refreshToken: null,
      user: null,
      setTokens: (access, refresh) =>
        set({ accessToken: access, refreshToken: refresh }),
      setUser: (user) => set({ user }),
      logout: () =>
        set({ accessToken: null, refreshToken: null, user: null }),
      isAuthenticated: () => !!get().accessToken && !!get().user,
    }),
    {
      name: "petroledger-auth",
      // Per-tab session: sessionStorage isolates auth between tabs so a
      // provider login in one tab does not clobber an admin login in another.
      storage: createJSONStorage(() => sessionStorage),
    },
  ),
);

export function roleHomePath(role: UserRole): string {
  switch (role) {
    case "superadmin":
    case "provider":
      return "/provider/dashboard";
    case "owner":
    case "admin":
      return "/admin/dashboard";
    case "manager":
      return "/manager/dashboard";
    case "worker":
      return "/worker/dashboard";
    default:
      return "/login";
  }
}

export function roleBasePath(role: UserRole): string {
  switch (role) {
    case "superadmin":
    case "provider":
      return "/provider";
    case "owner":
    case "admin":
      return "/admin";
    case "manager":
      return "/manager";
    case "worker":
      return "/worker";
    default:
      return "";
  }
}
