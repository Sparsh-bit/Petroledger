import { useEffect } from "react";
import { create } from "zustand";
import { persist } from "zustand/middleware";
import { api } from "../api/client";

export interface OrgSummary {
  id: string;
  name: string;
  slug?: string | null;
}

interface OrgState {
  orgs: OrgSummary[];
  selectedOrgId: string | null;
  setOrgs: (orgs: OrgSummary[]) => void;
  selectOrg: (id: string | null) => void;
  clear: () => void;
}

export const useOrgStore = create<OrgState>()(
  persist(
    (set) => ({
      orgs: [],
      selectedOrgId: null,
      setOrgs: (orgs) =>
        set((s) => {
          // Auto-select when only one org is visible, or when previous
          // selection is no longer valid.
          const stillValid = orgs.some((o) => o.id === s.selectedOrgId);
          const next =
            orgs.length === 1
              ? orgs[0].id
              : stillValid
                ? s.selectedOrgId
                : orgs[0]?.id ?? null;
          return { orgs, selectedOrgId: next };
        }),
      selectOrg: (id) => set({ selectedOrgId: id }),
      clear: () => set({ orgs: [], selectedOrgId: null }),
    }),
    { name: "petroledger-org" },
  ),
);

/**
 * One-shot fetch of the current user's visible organizations. Callable
 * from anywhere (not just React) — use this after any action that could
 * have implicitly created a new org (e.g. backend self-healing on first
 * pump create) so downstream pages see the fresh list.
 */
export async function refreshOrgs(): Promise<OrgSummary[]> {
  try {
    const res = await api.get<{ items: OrgSummary[] }>(
      "/organizations/?page=1&page_size=50",
    );
    const items = res.data?.items ?? [];
    useOrgStore.getState().setOrgs(items);
    return items;
  } catch {
    return [];
  }
}

/**
 * Ensure the org store is hydrated for the current session. Safe to call
 * from any admin page that relies on `selectedOrgId` — duplicate calls
 * across mounted pages are idempotent (no-op when orgs are already
 * loaded), and it closes the race where the header OrgSelector hasn't
 * yet made its first fetch.
 */
export function useEnsureOrgs(): void {
  const orgsLen = useOrgStore((s) => s.orgs.length);
  useEffect(() => {
    if (orgsLen > 0) return;
    void refreshOrgs();
  }, [orgsLen]);
}
