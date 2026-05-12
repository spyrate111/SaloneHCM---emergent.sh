import { Navigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function ProtectedRoute({ children, adminOnly = false, superAdminOnly = false }) {
  const { user, loading } = useAuth();
  if (loading) {
    return (
      <div className="min-h-screen grid place-items-center bg-[#F7F6F2]">
        <div className="text-sm text-[#525860]">Loading SaloneHCM…</div>
      </div>
    );
  }
  if (!user) return <Navigate to="/login" replace />;
  if (superAdminOnly && user.role !== "superadmin") return <Navigate to="/dashboard" replace />;
  if (adminOnly && user.role !== "admin" && user.role !== "superadmin") return <Navigate to="/dashboard" replace />;
  return children;
}
