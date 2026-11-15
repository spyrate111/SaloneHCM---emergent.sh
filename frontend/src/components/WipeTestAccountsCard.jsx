import { useState } from "react";
import api from "../lib/api";
import { toast } from "sonner";
import { Trash2, UserPlus } from "lucide-react";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader,
  AlertDialogTitle, AlertDialogTrigger,
} from "./ui/alert-dialog";

export const WipeTestAccountsCard = () => {
  const [busy, setBusy] = useState(null);

  const wipe = async () => {
    setBusy("wipe");
    try {
      const { data } = await api.delete("/users/test-accounts");
      toast.success(`Deleted ${data.deleted} test account${data.deleted === 1 ? "" : "s"}`);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Wipe failed");
    } finally { setBusy(null); }
  };

  const seed = async () => {
    setBusy("seed");
    try {
      const { data } = await api.post("/users/test-accounts/seed");
      toast.success(`Test accounts ready — ${data.created} created, ${data.updated} refreshed`);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Seeding failed");
    } finally { setBusy(null); }
  };

  return (
    <section className="bg-white border border-[#B03A2E]/30 rounded-xl p-6" data-testid="wipe-test-accounts-card">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <div className="text-[10px] uppercase tracking-[0.16em] text-[#B03A2E]">Danger zone · Super-admin</div>
          <h3 className="font-heading text-lg font-semibold mt-1">Test accounts</h3>
          <p className="text-sm text-[#686D76] mt-1 max-w-xl">
            Seed creates/refreshes the 70 standard test accounts (superadmin1…, hradmin1…, auditor1… etc.,
            passwords like Test@Auditor1) in this environment&rsquo;s database. Wipe permanently deletes them.
            Real accounts are never touched; both actions are audited.
          </p>
        </div>
        <div className="flex gap-2 flex-wrap">
          <button onClick={seed} disabled={!!busy}
            className="inline-flex items-center gap-2 text-sm bg-[#0A4A1E] hover:bg-[#063514] text-white px-4 py-2.5 rounded-lg disabled:opacity-50"
            data-testid="seed-test-accounts-btn">
            <UserPlus className="w-4 h-4" /> {busy === "seed" ? "Seeding… (~20s)" : "Seed test accounts"}
          </button>
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <button disabled={!!busy}
                className="inline-flex items-center gap-2 text-sm bg-[#B03A2E] hover:bg-[#93301F] text-white px-4 py-2.5 rounded-lg disabled:opacity-50"
                data-testid="wipe-test-accounts-btn">
                <Trash2 className="w-4 h-4" /> {busy === "wipe" ? "Wiping…" : "Wipe test accounts"}
              </button>
            </AlertDialogTrigger>
            <AlertDialogContent data-testid="wipe-test-accounts-dialog">
              <AlertDialogHeader>
                <AlertDialogTitle>Delete all test accounts?</AlertDialogTitle>
                <AlertDialogDescription>
                  This permanently deletes every user flagged <code>test_account</code> on a
                  salonehcm domain. This cannot be undone (Seed can recreate them).
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel data-testid="wipe-test-accounts-cancel">Cancel</AlertDialogCancel>
                <AlertDialogAction onClick={wipe} className="bg-[#B03A2E] hover:bg-[#93301F]"
                  data-testid="wipe-test-accounts-confirm">
                  Yes, delete them
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </div>
      </div>
    </section>
  );
};

export default WipeTestAccountsCard;
