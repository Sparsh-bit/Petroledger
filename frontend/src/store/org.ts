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
 * Ensure the org store is hydrated for the current session. Safe to call
 * from any admin page that relies on `selectedOrgId` — duplicate calls
 * across mounted pages are idempotent (no-op when orgs are already
 * loaded), and it closes the race where the header OrgSelector hasn't
 * yet made its first fetch.
 */
export function useEnsureOrgs(): void {
  const { orgs, setOrgs } = useOrgStore();
  useEffect(() => {
    if (orgs.length > 0) return;
    let cancel = false;
    void (async () => {
      try {
        const res = await api.get<{ items: OrgSummary[] }>(
          "/organizations/?page=1&page_size=50",
        );
        if (!cancel) setOrgs(res.data?.items ?? []);
      } catch {
        /* non-fatal — pages degrade to empty-state UIs */
      }
    })();
    return () => {
      cancel = true;
    };
  }, [orgs.length, setOrgs]);
}
