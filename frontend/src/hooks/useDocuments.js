import { useEffect, useState, useCallback } from "react";
import api from "../lib/api";
import { toast } from "sonner";

/**
 * useDocuments — encapsulates list/upload/download/delete + stats summary.
 * Returns: { docs, summary, employees, load, upload, download, remove,
 *            filterEmp, setFilterEmp, filterCat, setFilterCat, submitting }
 */
export function useDocuments({ isAdmin }) {
  const [docs, setDocs] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [summary, setSummary] = useState({ total: 0, by_category: [] });
  const [filterEmp, setFilterEmp] = useState("");
  const [filterCat, setFilterCat] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const load = useCallback(async () => {
    const params = {};
    if (isAdmin && filterEmp) params.employee_id = filterEmp;
    if (filterCat) params.category = filterCat;
    const r = await api.get("/documents", { params });
    setDocs(r.data);
    if (isAdmin) {
      try {
        const s = await api.get("/documents/stats/summary");
        setSummary(s.data);
      } catch (e) {
        console.warn("documents stats summary failed", e);
      }
    }
  }, [isAdmin, filterEmp, filterCat]);

  useEffect(() => {
    load();
    if (isAdmin) {
      api.get("/employees")
        .then((r) => setEmployees(r.data))
        .catch((e) => console.warn("employee list failed", e));
    }
  }, [load, isAdmin]);

  const upload = useCallback(async (formData) => {
    setSubmitting(true);
    try {
      await api.post("/documents/upload", formData, { headers: { "Content-Type": "multipart/form-data" } });
      toast.success("Document uploaded");
      await load();
      return true;
    } catch (e) {
      const d = e?.response?.data?.detail;
      toast.error(typeof d === "string" ? d : "Upload failed");
      return false;
    } finally {
      setSubmitting(false);
    }
  }, [load]);

  const download = useCallback(async (doc) => {
    try {
      const resp = await api.get(`/documents/${doc.id}/download`, { responseType: "blob" });
      const url = URL.createObjectURL(resp.data);
      const a = document.createElement("a");
      a.href = url; a.download = doc.original_filename; a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      console.error("download failed", e);
      toast.error("Download failed");
    }
  }, []);

  const remove = useCallback(async (doc) => {
    if (!window.confirm(`Delete "${doc.original_filename}"?`)) return;
    try {
      await api.delete(`/documents/${doc.id}`);
      toast.success("Document deleted");
      await load();
    } catch (e) {
      console.error("delete failed", e);
      toast.error("Delete failed");
    }
  }, [load]);

  return {
    docs, employees, summary, submitting,
    filterEmp, setFilterEmp, filterCat, setFilterCat,
    load, upload, download, remove,
  };
}
