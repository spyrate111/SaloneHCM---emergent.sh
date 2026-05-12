import { useEffect, useState, useCallback } from "react";
import api from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { toast } from "sonner";
import {
  Users as UsersIcon, UserPlus, Trash2, KeyRound, X, ShieldCheck, User as UserIcon, Crown, Search,
} from "lucide-react";

const ROLE_PILL = {
  superadmin: { label: "Super-admin", icon: Crown, color: "bg-[#FBE9DF] text-[#B84F2F]" },
  admin: { label: "Admin", icon: ShieldCheck, color: "bg-[#E5EEF6] text-[#26547C]" },
  employee: { label: "Employee", icon: UserIcon, color: "bg-[#EBE8E0] text-[#525860]" },
};

export default function Users() {
  const { user: me } = useAuth();
  const [users, setUsers] = useState([]);
  const [unlinked, setUnlinked] = useState([]);
  const [open, setOpen] = useState(false);
  const [resetting, setResetting] = useState(null);
  const [q, setQ] = useState("");

  const load = useCallback(async () => {
    const [u, e] = await Promise.all([
      api.get("/users"),
      api.get("/users/unlinked-employees").catch(() => ({ data: [] })),
    ]);
    setUsers(u.data);
    setUnlinked(e.data);
  }, []);

  useEffect(() => { load(); }, [load]);

  const onInvite = async (ev) => {
    ev.preventDefault();
    const fd = new FormData(ev.currentTarget);
    const payload = Object.fromEntries(fd.entries());
    if (!payload.employee_id) delete payload.employee_id;
    try {
      await api.post("/users/invite", payload);
      toast.success("User invited");
      setOpen(false);
      ev.currentTarget.reset();
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Invite failed");
    }
  };

  const onReset = async (ev) => {
    ev.preventDefault();
    const fd = new FormData(ev.currentTarget);
    try {
      await api.post(`/users/${resetting.id}/reset-password`, { password: fd.get("password") });
      toast.success("Password reset");
      setResetting(null);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Reset failed");
    }
  };

  const onDelete = async (u) => {
    if (!window.confirm(`Delete user ${u.email}?`)) return;
    try {
      await api.delete(`/users/${u.id}`);
      toast.success("User deleted");
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Delete failed");
    }
  };

  const filtered = users.filter((u) => {
    if (!q) return true;
    const t = q.toLowerCase();
    return u.email.toLowerCase().includes(t) || u.name?.toLowerCase().includes(t);
  });

  return (
    <div className="space-y-6" data-testid="users-page">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <div className="text-[11px] uppercase tracking-[0.18em] text-[#525860]">Users & Access</div>
          <h1 className="font-heading text-3xl sm:text-4xl font-bold mt-1">Team accounts</h1>
          <p className="text-[#525860] text-sm mt-1.5 max-w-2xl">
            Invite admins and employees to your SaloneHCM tenant. Optionally link new user accounts to existing employee records.
          </p>
        </div>
        <button
          data-testid="users-invite-open"
          onClick={() => setOpen(true)}
          className="inline-flex items-center gap-2 bg-[#133326] hover:bg-[#0F281E] text-white text-sm px-4 py-2.5 rounded-md transition"
        >
          <UserPlus className="w-4 h-4" strokeWidth={1.5} /> Invite user
        </button>
      </div>

      <div className="bg-white border border-[#E2DFD6] rounded-lg overflow-hidden">
        <div className="px-5 py-4 border-b border-[#E2DFD6] flex items-center gap-3">
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#A1A5AB]" strokeWidth={1.5} />
            <input
              data-testid="users-search"
              placeholder="Search name or email…"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              className="w-full bg-[#F7F6F2] border border-[#E2DFD6] rounded-md pl-9 pr-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#26547C]"
            />
          </div>
          <div className="text-xs text-[#686D76] font-data">{filtered.length} of {users.length} users</div>
        </div>
        <table className="w-full text-sm">
          <thead className="bg-[#F7F6F2]">
            <tr>
              {["User", "Role", "Linked employee", "Invited", ""].map((h) => (
                <th key={h} className="text-left text-[10px] uppercase tracking-wider text-[#525860] py-3 px-4 font-medium">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.map((u) => {
              const rolePill = ROLE_PILL[u.role] || ROLE_PILL.employee;
              const RoleIcon = rolePill.icon;
              return (
                <tr key={u.id} className="border-t border-[#E2DFD6] hover:bg-[#FDFCFB]" data-testid={`user-row-${u.id}`}>
                  <td className="py-3 px-4">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-full bg-[#F1EEE6] grid place-items-center text-xs font-medium text-[#133326]">
                        {u.name?.[0] || "?"}
                      </div>
                      <div>
                        <div className="font-medium">{u.name}</div>
                        <div className="text-xs text-[#686D76] font-data">{u.email}</div>
                      </div>
                    </div>
                  </td>
                  <td className="py-3 px-4">
                    <span className={`inline-flex items-center gap-1.5 text-[11px] uppercase tracking-wider px-2 py-0.5 rounded-full ${rolePill.color}`}>
                      <RoleIcon className="w-3 h-3" strokeWidth={1.7} /> {rolePill.label}
                    </span>
                  </td>
                  <td className="py-3 px-4 text-[#525860] text-xs font-data">{u.employee_id ? u.employee_id.slice(0, 8) + "…" : "—"}</td>
                  <td className="py-3 px-4 text-[#686D76] text-xs font-data">{u.created_at ? new Date(u.created_at).toLocaleDateString() : "—"}</td>
                  <td className="py-3 px-4 text-right">
                    <div className="inline-flex items-center gap-1">
                      {u.role !== "superadmin" && (
                        <>
                          <button
                            data-testid={`user-reset-${u.id}`}
                            onClick={() => setResetting(u)}
                            className="p-1.5 rounded hover:bg-[#F1EEE6] text-[#26547C]"
                            title="Reset password"
                          >
                            <KeyRound className="w-4 h-4" strokeWidth={1.5} />
                          </button>
                          {u.id !== me?.id && (
                            <button
                              data-testid={`user-delete-${u.id}`}
                              onClick={() => onDelete(u)}
                              className="p-1.5 rounded hover:bg-[#FBEAEA] text-[#B83A3A]"
                              title="Delete"
                            >
                              <Trash2 className="w-4 h-4" strokeWidth={1.5} />
                            </button>
                          )}
                        </>
                      )}
                    </div>
                  </td>
                </tr>
              );
            })}
            {!filtered.length && (
              <tr><td colSpan={5} className="py-10 text-center text-sm text-[#686D76]">
                <UsersIcon className="w-8 h-8 mx-auto mb-2 text-[#A1A5AB]" strokeWidth={1.3} />
                {q ? "No users match your search." : "No users yet — invite the first one."}
              </td></tr>
            )}
          </tbody>
        </table>
      </div>

      {open && (
        <div className="fixed inset-0 z-40 bg-black/40 grid place-items-center p-4" data-testid="invite-modal">
          <form onSubmit={onInvite} className="bg-white rounded-lg border border-[#E2DFD6] w-full max-w-md p-6 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="font-heading text-lg font-semibold">Invite user</h3>
              <button type="button" onClick={() => setOpen(false)} className="text-[#525860] hover:text-[#1A1C1E]">
                <X className="w-4 h-4" />
              </button>
            </div>
            <Field label="Full name"><input data-testid="invite-name" required name="name" placeholder="Jane Doe" className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm" /></Field>
            <Field label="Email"><input data-testid="invite-email" required type="email" name="email" placeholder="jane@company.sl" className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm" /></Field>
            <Field label="Role">
              <select data-testid="invite-role" required name="role" defaultValue="employee" className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm">
                <option value="employee">Employee</option>
                <option value="admin">Admin</option>
              </select>
            </Field>
            <Field label="Initial password (share securely)">
              <input data-testid="invite-password" required name="password" type="password" minLength={8} placeholder="At least 8 chars" className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm font-data" />
            </Field>
            {unlinked.length > 0 && (
              <Field label="Link to existing employee (optional)">
                <select data-testid="invite-employee" name="employee_id" defaultValue="" className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm">
                  <option value="">— None —</option>
                  {unlinked.map((e) => (
                    <option key={e.id} value={e.id}>{e.first_name} {e.last_name} · {e.department}</option>
                  ))}
                </select>
              </Field>
            )}
            <div className="flex items-center justify-end gap-2 pt-2">
              <button type="button" onClick={() => setOpen(false)} className="text-sm px-4 py-2 rounded-md border border-[#E2DFD6] hover:bg-[#F7F6F2]">Cancel</button>
              <button type="submit" data-testid="invite-submit" className="inline-flex items-center gap-2 text-sm bg-[#133326] hover:bg-[#0F281E] text-white px-4 py-2 rounded-md">
                <UserPlus className="w-4 h-4" strokeWidth={1.5} /> Send invite
              </button>
            </div>
          </form>
        </div>
      )}

      {resetting && (
        <div className="fixed inset-0 z-40 bg-black/40 grid place-items-center p-4" data-testid="reset-modal">
          <form onSubmit={onReset} className="bg-white rounded-lg border border-[#E2DFD6] w-full max-w-sm p-6 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="font-heading text-lg font-semibold">Reset password</h3>
              <button type="button" onClick={() => setResetting(null)} className="text-[#525860]"><X className="w-4 h-4" /></button>
            </div>
            <p className="text-xs text-[#525860]">New password for <span className="font-medium text-[#1A1C1E]">{resetting.email}</span>.</p>
            <input required name="password" type="password" minLength={8} placeholder="New password (8+ chars)" className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm font-data" />
            <div className="flex items-center justify-end gap-2">
              <button type="button" onClick={() => setResetting(null)} className="text-sm px-4 py-2 rounded-md border border-[#E2DFD6]">Cancel</button>
              <button type="submit" data-testid="reset-submit" className="text-sm bg-[#133326] text-white px-4 py-2 rounded-md">Save</button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}

function Field({ label, children }) {
  return (
    <div>
      <label className="block text-[11px] uppercase tracking-wider text-[#525860] mb-1">{label}</label>
      {children}
    </div>
  );
}
