import { Mail, KeyRound, UserPlus, X } from "lucide-react";

export const InviteUserModal = ({ inviteMode, setInviteMode, unlinked, onInvite, onClose }) => (
  <div className="fixed inset-0 z-40 bg-black/40 grid place-items-center p-4" data-testid="invite-modal">
    <form onSubmit={onInvite} className="bg-white rounded-lg border border-[#E2DFD6] w-full max-w-md p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="font-heading text-lg font-semibold">Invite user</h3>
        <button type="button" onClick={onClose} className="text-[#525860] hover:text-[#1A1C1E]">
          <X className="w-4 h-4" />
        </button>
      </div>
      <div className="flex gap-2 p-1 bg-[#F7F6F2] border border-[#E2DFD6] rounded-md" data-testid="invite-mode-toggle">
        <button type="button" onClick={() => setInviteMode("magic")} data-testid="invite-mode-magic" className={`flex-1 text-xs font-medium px-3 py-2 rounded inline-flex items-center justify-center gap-1.5 transition ${inviteMode === "magic" ? "bg-white text-[#0A4A1E] shadow-sm" : "text-[#686D76]"}`}>
          <Mail className="w-3.5 h-3.5" /> Magic link
        </button>
        <button type="button" onClick={() => setInviteMode("password")} data-testid="invite-mode-password" className={`flex-1 text-xs font-medium px-3 py-2 rounded inline-flex items-center justify-center gap-1.5 transition ${inviteMode === "password" ? "bg-white text-[#0A4A1E] shadow-sm" : "text-[#686D76]"}`}>
          <KeyRound className="w-3.5 h-3.5" /> Set password
        </button>
      </div>
      <div className="text-[11px] text-[#525860] -mt-2">
        {inviteMode === "magic"
          ? "Sends an email with a one-time link — the user sets their own password on first click."
          : "Creates the account immediately with the password you choose."}
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
        <input
          data-testid="invite-password"
          required={inviteMode === "password"}
          disabled={inviteMode === "magic"}
          name="password"
          type="password"
          minLength={8}
          placeholder={inviteMode === "magic" ? "(set on first click)" : "At least 8 chars"}
          className="w-full bg-white border border-[#E2DFD6] rounded-md px-3 py-2 text-sm font-data disabled:bg-[#F7F6F2] disabled:text-[#A1A5AB]"
        />
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
        <button type="button" onClick={onClose} className="text-sm px-4 py-2 rounded-md border border-[#E2DFD6] hover:bg-[#F7F6F2]">Cancel</button>
        <button type="submit" data-testid="invite-submit" className="inline-flex items-center gap-2 text-sm bg-[#0A4A1E] hover:bg-[#063514] text-white px-4 py-2 rounded-md">
          {inviteMode === "magic" ? <Mail className="w-4 h-4" strokeWidth={1.5} /> : <UserPlus className="w-4 h-4" strokeWidth={1.5} />}
          {inviteMode === "magic" ? "Send magic link" : "Create account"}
        </button>
      </div>
    </form>
  </div>
);

function Field({ label, children }) {
  return (
    <div>
      <label className="block text-[11px] uppercase tracking-wider text-[#525860] mb-1">{label}</label>
      {children}
    </div>
  );
}
