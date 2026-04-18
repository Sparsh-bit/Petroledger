import { create } from "zustand";
import { persist } from "zustand/middleware";

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
