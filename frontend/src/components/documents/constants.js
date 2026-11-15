import {
  FileSignature, Award, Receipt, FileText, IdCard, Folder,
} from "lucide-react";

export const CATEGORIES = [
  { id: "contract", label: "Contract", icon: FileSignature, color: "bg-[#E4F7E7] text-[#17A035]" },
  { id: "certificate", label: "Certificate", icon: Award, color: "bg-[#FBF1DE] text-[#8B6A14]" },
  { id: "p9_form", label: "P9 / Tax Form", icon: Receipt, color: "bg-[#E5EEF6] text-[#26547C]" },
  { id: "payslip", label: "Payslip", icon: FileText, color: "bg-[#FBE9DF] text-[#B84F2F]" },
  { id: "id_document", label: "ID Document", icon: IdCard, color: "bg-[#E5EDF7] text-[#2A5C9C]" },
  { id: "other", label: "Other", icon: Folder, color: "bg-[#EBE8E0] text-[#525860]" },
];

export const CAT_BY_ID = Object.fromEntries(CATEGORIES.map((c) => [c.id, c]));

export const ACCEPT = ".pdf,.docx,.doc,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document";

export const fmtBytes = (n) => {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(2)} MB`;
};
