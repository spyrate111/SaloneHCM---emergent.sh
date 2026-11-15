import { FolderOpen, Trash, Share2, BarChart3 } from "lucide-react";

const STATUS_BG = {
  draft: "bg-[#EBE8E0] text-[#525860]",
  pending: "bg-[#FBF1DE] text-[#8B6A14]",
  approved: "bg-[#E4F7E7] text-[#17A035]",
  rejected: "bg-[#E9F2FB] text-[#3A7CB8]",
};

const HEADERS = ["", "Title", "Status", "Description", "Rules", "Created by", ""];

export default function SavedScenariosTable({
  saved, compareIds, toggleCompare, runCompare,
  loadScenario, deleteScenario, onShare,
}) {
  if (!saved.length) return null;
  return (
    <div className="bg-white border border-[#E2DFD6] rounded-lg overflow-hidden" data-testid="saved-scenarios">
      <div className="px-6 py-4 border-b border-[#E2DFD6] flex items-center justify-between flex-wrap gap-3">
        <div>
          <h3 className="font-heading text-lg font-semibold flex items-center gap-2"><FolderOpen className="w-4 h-4" /> Saved scenarios</h3>
          <p className="text-xs text-[#686D76] mt-0.5">Click a row to load. Tick 2+ to compare side-by-side.</p>
        </div>
        {compareIds.size >= 2 && (
          <button data-testid="compare-button" onClick={runCompare} className="inline-flex items-center gap-1.5 text-sm bg-[#26547C] hover:bg-[#1D4363] text-white px-4 py-2 rounded-md">
            <BarChart3 className="w-3.5 h-3.5" /> Compare {compareIds.size} selected
          </button>
        )}
      </div>
      <table className="w-full text-sm">
        <thead className="bg-[#F7F6F2]">
          <tr>{HEADERS.map((h, i) => (
            <th key={`h-${i}-${h}`} className="text-left text-[10px] uppercase tracking-wider text-[#525860] py-3 px-4 font-medium">{h}</th>
          ))}</tr>
        </thead>
        <tbody>
          {saved.map((s) => (
            <SavedRow
              key={s.id} s={s}
              checked={compareIds.has(s.id)}
              onToggle={toggleCompare}
              onLoad={loadScenario}
              onDelete={deleteScenario}
              onShare={onShare}
            />
          ))}
        </tbody>
      </table>
    </div>
  );
}

function SavedRow({ s, checked, onToggle, onLoad, onDelete, onShare }) {
  return (
    <tr className="border-t border-[#E2DFD6] hover:bg-[#FDFCFB]">
      <td className="py-3 px-4">
        <input type="checkbox" data-testid={`compare-${s.id}`} checked={checked} onChange={() => onToggle(s.id)} className="w-4 h-4 accent-[#26547C] cursor-pointer" />
      </td>
      <td className="py-3 px-4 font-medium cursor-pointer" onClick={() => onLoad(s.id)}>{s.title}</td>
      <td className="py-3 px-4">
        <span className={`text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-full ${STATUS_BG[s.approval_status] || STATUS_BG.draft}`}>
          {s.approval_status}{s.applied ? " · applied" : ""}
        </span>
      </td>
      <td className="py-3 px-4 text-[#686D76] text-xs max-w-md truncate">{s.description || "—"}</td>
      <td className="py-3 px-4 font-data text-[#525860]">{s.rules.length}</td>
      <td className="py-3 px-4 text-xs text-[#686D76]">{s.created_by}</td>
      <td className="py-3 px-4 text-right">
        <div className="inline-flex gap-1">
          <button title="Share" onClick={() => onShare(s.id)} className="p-1.5 rounded text-[#26547C] hover:bg-[#E5EEF6]"><Share2 className="w-3.5 h-3.5" /></button>
          <button title="Load" onClick={() => onLoad(s.id)} className="p-1.5 rounded text-[#17A035] hover:bg-[#E4F7E7]"><FolderOpen className="w-3.5 h-3.5" /></button>
          <button title="Delete" onClick={() => onDelete(s.id)} className="p-1.5 rounded text-[#3A7CB8] hover:bg-[#E9F2FB]"><Trash className="w-3.5 h-3.5" /></button>
        </div>
      </td>
    </tr>
  );
}
