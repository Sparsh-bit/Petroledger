import { useEffect, useState } from "react";
import toast from "react-hot-toast";
import { Search } from "lucide-react";
import { Badge } from "../../components/ui";
import { Select } from "../../components/ui/Select";
import { DataTable, Pagination } from "../../components/ui/DataTable";
import { PageHeader } from "../../components/ui/PageHeader";
import { providerApi, ProviderUserItem } from "../../api/provider";

const ROLES = ["", "owner", "admin", "manager", "worker", "superadmin", "provider"];

function errMsg(err: unknown, fallback: string): string {
  const e = err as { response?: { data?: { detail?: string } }; message?: string };
  return e?.response?.data?.detail || e?.message || fallback;
}

export default function ProviderUsersPage() {
  const [items, setItems] = useState<ProviderUserItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [role, setRole] = useState("");
  const [loading, setLoading] = useState(true);
  const pageSize = 50;

  async function load() {
    setLoading(true);
    try {
      const r = await providerApi.getUsers({
        page,
        page_size: pageSize,
        search: search || undefined,
        role: role || undefined,
      });
      setItems(r.items);
      setTotal(r.total);
    } catch (err) {
      toast.error(errMsg(err, "Failed to load users."));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, search, role]);

  async function toggleActive(u: ProviderUserItem) {
    try {
      if (u.is_active) {
        await providerApi.deactivateUser(u.id);
        toast.success("User deactivated.");
      } else {
        await providerApi.reactivateUser(u.id);
        toast.success("User reactivated.");
      }
      void load();
    } catch (err) {
      toast.error(errMsg(err, "Failed to update user."));
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Users"
        description="All users across all tenants."
      />

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div className="relative sm:col-span-2">
          <Search className="h-4 w-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            value={search}
            onChange={(e) => {
              setPage(1);
              setSearch(e.target.value);
            }}
            placeholder="Search email…"
            className="w-full pl-9 pr-3 py-2.5 rounded-lg border border-slate-300 bg-white text-sm text-slate-900 outline-none focus:border-slate-400"
          />
        </div>
        <Select
          value={role}
          onChange={(e) => {
            setPage(1);
            setRole(e.target.value);
          }}
        >
          <option value="">All roles</option>
          {ROLES.filter(Boolean).map((r) => (
            <option key={r} value={r}>
              {r}
            </option>
          ))}
        </Select>
      </div>

      <DataTable<ProviderUserItem>
        data={items}
        loading={loading}
        rowKey={(u) => u.id}
        emptyState="No users match these filters."
        columns={[
          {
            key: "email",
            header: "Email",
            render: (u) => (
              <span className="font-medium text-slate-900">{u.email}</span>
            ),
          },
          {
            key: "role",
            header: "Role",
            render: (u) => <Badge tone="indigo">{u.role}</Badge>,
          },
          {
            key: "tenant",
            header: "Tenant",
            render: (u) => u.tenant_name ?? "—",
          },
          {
            key: "last_login",
            header: "Last login",
            render: (u) =>
              u.last_login
                ? new Date(u.last_login).toLocaleString()
                : "Never",
          },
          {
            key: "status",
            header: "Status",
            render: (u) => (
              <Badge tone={u.is_active ? "green" : "slate"}>
                {u.is_active ? "active" : "inactive"}
              </Badge>
            ),
          },
          {
            key: "actions",
            header: "",
            align: "right",
            render: (u) => (
              <button
                type="button"
                onClick={() => void toggleActive(u)}
                className="text-xs text-indigo-600 hover:text-indigo-500"
              >
                {u.is_active ? "Deactivate" : "Reactivate"}
              </button>
            ),
          },
        ]}
      />

      <Pagination
        page={page}
        pageSize={pageSize}
        total={total}
        onPageChange={setPage}
      />
    </div>
  );
}
