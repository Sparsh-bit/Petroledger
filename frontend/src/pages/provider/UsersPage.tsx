import { useEffect, useState } from "react";
import { Search } from "lucide-react";
import { Badge, Card } from "../../components/ui";
import { Spinner } from "../../components/ui/Spinner";
import { providerApi, type ProviderUserItem } from "../../api/provider";

const ROLES = ["", "owner", "admin", "manager", "worker", "superadmin", "provider"];

export default function ProviderUsersPage() {
  const [items, setItems] = useState<ProviderUserItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [role, setRole] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const pageSize = 50;

  useEffect(() => {
    setLoading(true);
    setError(null);
    providerApi
      .users({
        page,
        page_size: pageSize,
        search: search || undefined,
        role: role || undefined,
      })
      .then((r) => {
        setItems(r.items);
        setTotal(r.total);
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [page, search, role]);

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Users</h1>
        <p className="mt-1 text-ink-400 text-sm">
          All users across all tenants. Filter by role or search by email.
        </p>
      </div>

      <Card className="p-4">
        <div className="flex flex-wrap items-center gap-3">
          <div className="relative flex-1 min-w-[220px]">
            <Search className="h-4 w-4 absolute left-3 top-1/2 -translate-y-1/2 text-ink-500" />
            <input
              value={search}
              onChange={(e) => {
                setPage(1);
                setSearch(e.target.value);
              }}
              placeholder="Search email…"
              className="w-full pl-9 pr-3 py-2 rounded-lg border border-ink-700 bg-ink-900/60 text-sm outline-none focus:border-brand-400"
            />
          </div>
          <select
            value={role}
            onChange={(e) => {
              setPage(1);
              setRole(e.target.value);
            }}
            className="rounded-lg border border-ink-700 bg-ink-900/60 px-3 py-2 text-sm"
          >
            {ROLES.map((r) => (
              <option key={r} value={r}>
                {r === "" ? "All roles" : r}
              </option>
            ))}
          </select>
          <div className="text-sm text-ink-500">
            {total.toLocaleString()} user{total === 1 ? "" : "s"}
          </div>
        </div>
      </Card>

      {error && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-200">
          {error}
        </div>
      )}

      <Card className="p-0 overflow-hidden">
        {loading ? (
          <div className="p-8">
            <Spinner label="Loading users…" />
          </div>
        ) : items.length === 0 ? (
          <div className="p-8 text-center text-sm text-ink-500">
            No users match these filters.
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-ink-900/80 text-xs uppercase text-ink-400">
              <tr>
                <th className="text-left px-5 py-3">Email</th>
                <th className="text-left px-5 py-3">Role</th>
                <th className="text-left px-5 py-3">Tenant</th>
                <th className="text-left px-5 py-3">Last login</th>
                <th className="text-left px-5 py-3">Status</th>
              </tr>
            </thead>
            <tbody>
              {items.map((u) => (
                <tr key={u.id} className="border-t border-ink-800">
                  <td className="px-5 py-3 font-medium">{u.email}</td>
                  <td className="px-5 py-3">
                    <Badge tone="blue">{u.role}</Badge>
                  </td>
                  <td className="px-5 py-3 text-ink-300">
                    {u.tenant_name ?? "—"}
                  </td>
                  <td className="px-5 py-3 text-ink-400">
                    {u.last_login
                      ? new Date(u.last_login).toLocaleString()
                      : "Never"}
                  </td>
                  <td className="px-5 py-3">
                    <Badge tone={u.is_active ? "green" : "slate"}>
                      {u.is_active ? "active" : "inactive"}
                    </Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      {totalPages > 1 && (
        <div className="flex items-center justify-between text-sm">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page <= 1}
            className="rounded-lg border border-ink-700 px-3 py-1.5 hover:bg-ink-800 disabled:opacity-40"
          >
            Previous
          </button>
          <div className="text-ink-400">
            Page {page} of {totalPages}
          </div>
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page >= totalPages}
            className="rounded-lg border border-ink-700 px-3 py-1.5 hover:bg-ink-800 disabled:opacity-40"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
