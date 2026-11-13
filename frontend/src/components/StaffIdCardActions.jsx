import { useEffect, useState } from "react";
import api, { downloadBlob } from "../lib/api";
import { toast } from "sonner";
import { BadgeCheck, Camera, Download, Loader2 } from "lucide-react";

export default function StaffIdCardActions({ employee }) {
  const [photoUrl, setPhotoUrl] = useState(null);
  const [photoReady, setPhotoReady] = useState(false);
  const [photoLoading, setPhotoLoading] = useState(true);
  const [photoVersion, setPhotoVersion] = useState(0);
  const [uploading, setUploading] = useState(false);
  const [printing, setPrinting] = useState(false);

  useEffect(() => {
    let cancelled = false;
    let objectUrl = null;
    setPhotoLoading(true);
    setPhotoReady(false);
    setPhotoUrl(null);
    api.get("/employees/" + encodeURIComponent(employee.id) + "/id-photo", { responseType: "blob" })
      .then((r) => {
        objectUrl = URL.createObjectURL(r.data);
        if (!cancelled) {
          setPhotoUrl(objectUrl);
          setPhotoReady(true);
        } else {
          URL.revokeObjectURL(objectUrl);
        }
      })
      .catch(() => {
        if (!cancelled) setPhotoReady(false);
      })
      .finally(() => {
        if (!cancelled) setPhotoLoading(false);
      });
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [employee.id, photoVersion]);

  const uploadPhoto = async (ev) => {
    const file = ev.target.files?.[0];
    if (!file) return;
    if (file.size > 5 * 1024 * 1024) {
      toast.error("Choose an image smaller than 5 MB");
      ev.target.value = "";
      return;
    }
    const form = new FormData();
    form.append("file", file);
    setUploading(true);
    try {
      await api.post(
        "/employees/" + encodeURIComponent(employee.id) + "/id-photo",
        form,
      );
      setPhotoVersion((v) => v + 1);
      toast.success("Staff photo saved");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not save staff photo");
    } finally {
      setUploading(false);
      ev.target.value = "";
    }
  };

  const printCard = async () => {
    if (!photoReady) {
      toast.error("Upload a photo before printing the staff ID");
      return;
    }
    setPrinting(true);
    try {
      await downloadBlob(
        "/employees/" + encodeURIComponent(employee.id) + "/id-card.pdf",
        "staff-id-" + (employee.last_name || "employee").replace(/\s/g, "_") + ".pdf",
      );
      toast.success("Staff ID card downloaded");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not generate staff ID card");
    } finally {
      setPrinting(false);
    }
  };

  return (
    <section className="bg-white border border-[#E2DFD6] rounded-lg p-6 space-y-4" data-testid="staff-id-card-panel">
      <div>
        <h3 className="font-heading text-lg font-semibold inline-flex items-center gap-2">
          <BadgeCheck className="w-5 h-5 text-[#0A4A1E]" strokeWidth={1.5} />
          Staff ID card
        </h3>
        <p className="text-xs text-[#686D76] mt-1">
          Add a staff photo, then print a card with the employee’s role, department, and a QR link to mobile clock-in.
        </p>
      </div>
      <div className="flex items-center gap-4 flex-wrap">
        <div className="w-16 h-20 rounded-md border border-[#E2DFD6] bg-[#F7F6F2] overflow-hidden grid place-items-center">
          {photoUrl
            ? <img src={photoUrl} alt={employee.first_name + " " + employee.last_name} className="w-full h-full object-cover" data-testid="staff-id-photo-preview" />
            : photoLoading
            ? <Loader2 className="w-5 h-5 text-[#525860] animate-spin" />
            : <Camera className="w-5 h-5 text-[#A1A5AB]" />}
        </div>
        <div className="flex-1 min-w-[180px]">
          <div className="text-sm font-medium text-[#1A1C1E]">{employee.first_name} {employee.last_name}</div>
          <div className="text-xs text-[#686D76]">{employee.job_title} · {employee.department}</div>
          <div className="text-[10px] text-[#686D76] mt-1">
            {photoReady ? "Photo ready for printing" : "Upload a clear JPEG or PNG photo (100 × 100 px minimum)"}
          </div>
        </div>
        <div className="flex gap-2">
          <label className="inline-flex items-center gap-1.5 text-xs border border-[#E2DFD6] px-3 py-2 rounded-md cursor-pointer hover:bg-[#F7F6F2]">
            <Camera className="w-3.5 h-3.5" />
            {uploading ? "Uploading…" : photoReady ? "Replace photo" : "Upload photo"}
            <input
              type="file"
              accept="image/jpeg,image/png"
              onChange={uploadPhoto}
              disabled={uploading}
              className="sr-only"
              data-testid="staff-id-photo-input"
            />
          </label>
          <button
            type="button"
            onClick={printCard}
            disabled={!photoReady || printing || photoLoading}
            className="inline-flex items-center gap-1.5 text-xs bg-[#0A4A1E] hover:bg-[#063514] text-white px-3 py-2 rounded-md disabled:opacity-50"
            data-testid="staff-id-print"
          >
            <Download className="w-3.5 h-3.5" /> {printing ? "Preparing…" : "Print ID"}
          </button>
        </div>
      </div>
    </section>
  );
}
