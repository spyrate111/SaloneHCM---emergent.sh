import { FileText, Image as ImageIcon, Download, Trash2, FolderArchive } from "lucide-react";
import { CAT_BY_ID, fmtBytes } from "./constants";

export default function DocumentsTable({ docs, isAdmin, onDownload, onDelete, hasFilters }) {
  if (!docs.length) {
    return (
      <tr><td colSpan={6} className="py-12 text-center text-sm text-[#686D76]">
        <FolderArchive className="w-8 h-8 mx-auto mb-2 text-[#A1A5AB]" strokeWidth={1.3} />
        {hasFilters
          ? "No documents match these filters."
          : (isAdmin ? "No documents yet — upload the first one." : "No documents have been shared with you yet.")}
      </td></tr>
    );
  }
  return docs.map((d) => {
    const cat = CAT_BY_ID[d.category] || CAT_BY_ID.other;
    const Icon = (d.content_type || "").startsWith("image/") ? ImageIcon : FileText;
    return (
      <tr key={d.id} className="border-t border-[#E2DFD6] hover:bg-[#FDFCFB]" data-testid={`doc-row-${d.id}`}>
        <td className="py-3 px-4">
          <div className="flex items-start gap-2.5">
            <div className="w-8 h-8 rounded-md bg-[#F7F6F2] border border-[#E2DFD6] grid place-items-center text-[#525860]">
              <Icon className="w-4 h-4" strokeWidth={1.5} />
            </div>
            <div className="min-w-0">
              <div className="font-medium truncate max-w-[260px]" title={d.original_filename}>{d.original_filename}</div>
              {d.description && <div className="text-xs text-[#686D76] truncate max-w-[260px]">{d.description}</div>}
            </div>
          </div>
        </td>
        <td className="py-3 px-4 text-[#525860]">{isAdmin ? d.employee_name : d.uploaded_by}</td>
        <td className="py-3 px-4">
          <span className={`inline-flex items-center gap-1.5 text-[11px] uppercase tracking-wider px-2 py-0.5 rounded-full ${cat.color}`}>
            <cat.icon className="w-3 h-3" strokeWidth={1.7} /> {cat.label}
          </span>
        </td>
        <td className="py-3 px-4 font-data text-[#525860] text-xs">{fmtBytes(d.size)}</td>
        <td className="py-3 px-4 font-data text-[#686D76] text-xs">{new Date(d.uploaded_at).toLocaleDateString()}</td>
        <td className="py-3 px-4 text-right">
          <div className="inline-flex items-center gap-1">
            <button
              data-testid={`doc-download-${d.id}`}
              onClick={() => onDownload(d)}
              className="p-1.5 rounded hover:bg-[#F1EEE6] text-[#26547C]"
              title="Download"
            >
              <Download className="w-4 h-4" strokeWidth={1.5} />
            </button>
            {isAdmin && (
              <button
                data-testid={`doc-delete-${d.id}`}
                onClick={() => onDelete(d)}
                className="p-1.5 rounded hover:bg-[#E9F2FB] text-[#3A7CB8]"
                title="Delete"
              >
                <Trash2 className="w-4 h-4" strokeWidth={1.5} />
              </button>
            )}
          </div>
        </td>
      </tr>
    );
  });
}
