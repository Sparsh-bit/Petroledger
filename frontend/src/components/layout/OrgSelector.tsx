import { useEffect } from "react";
import { api } from "../../api/client";
import { useOrgStore, OrgSummary } from "../../store/org";
import { useAuth } from "../../store/auth";

interface Paged<T> {
  items: T[];
  total: number;
}

export function OrgSelector() {
  const { user } = useAuth();
  const { orgs, selectedOrgId, setOrgs, selectOrg } = useOrgStore();

  useEffect(() => {
    if (!user) return;
    void (async () => {
      try {
        const res = await api.get<Paged<OrgSummary>>(
          "/organizations/?page=1&page_size=50",
        );
        setOrgs(res.data?.items ?? []);
      } catch {
        setOrgs([]);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.id]);

  if (!user) return null;
  if (orgs.length <= 1) return null;

  return (
    <label className="text-xs text-slate-600 flex items-center gap-2">
      <span className="uppercase tracking-wider">Org</span>
      <select
        value={selectedOrgId ?? ""}
        onChange={(e) => selectOrg(e.target.value || null)}
        className="rounded-md border border-slate-300 bg-white px-2 py-1 text-sm text-slate-900 focus:border-slate-500 outline-none"
      >
        {orgs.map((o) => (
          <option key={o.id} value={o.id}>
            {o.name}
          </option>
        ))}
      </select>
    </label>
  );
}
