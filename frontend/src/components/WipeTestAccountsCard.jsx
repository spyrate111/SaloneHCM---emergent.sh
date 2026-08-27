import { useState } from "react";
import api from "../lib/api";
import { toast } from "sonner";
import { Trash2 } from "lucide-react";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader,
  AlertDialogTitle, AlertDialogTrigger,
} from "./ui/alert-dialog";

export const WipeTestAccountsCard = () => {
  const [busy, setBusy] = useState(false);

  const wipe = async () => {
    setBusy(true);
    try {
      const { data } = await api.delete("/users/test-accounts");
      toast.success(`Deleted ${data.deleted} test account${data.deleted === 1 ? "" : "s"}`);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Wipe failed");
    } finally { setBusy(false); }
  };

  return (
    <section className="bg-white border border-[#B03A2E]/30 rounded-xl p-6" data-testid="wipe-test-accounts-card">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <div className="text-[10px] uppercase tracking-[0.16em] text-[#B03A2E]">Danger zone · Super-admin</div>
          <h3 className="font-heading text-lg font-semibold mt-1">Wipe test accounts</h3>
          <p className="text-sm text-[#686D76] mt-1 max-w-xl">
            Permanently deletes every seeded account flagged as a test account on a salonehcm domain
            (superadmin1…, hradmin1…, auditor1… etc.). Real accounts are never touched. The action is audited.
          </p>
        </div>
        <AlertDialog>
          <AlertDialogTrigger asChild>
            <button disabled={busy}
              className="inline-flex items-center gap-2 text-sm bg-[#B03A2E] hover:bg-[#93301F] text-white px-4 py-2.5 rounded-lg disabled:opacity-50"
              data-testid="wipe-test-accounts-btn">
              <Trash2 className="w-4 h-4" /> {busy ? "Wiping…" : "Wipe test accounts"}
            </button>
          </AlertDialogTrigger>
          <AlertDialogContent data-testid="wipe-test-accounts-dialog">
            <AlertDialogHeader>
              <AlertDialogTitle>Delete all test accounts?</AlertDialogTitle>
              <AlertDialogDescription>
                This permanently deletes every user flagged <code>test_account</code> on a
                salonehcm domain. This cannot be undone (the seed script can recreate them).
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
    </section>
  );
};

export default WipeTestAccountsCard;
