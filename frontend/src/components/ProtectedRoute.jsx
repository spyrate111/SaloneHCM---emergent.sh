import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import AccessDenied from "./AccessDenied";

export default function ProtectedRoute({ children, adminOnly = false, superAdminOnly = false, roles = null }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) {
    return (
      <div className="min-h-screen grid place-items-center bg-[#F7F6F2]">
        <div className="w-8 h-8 border-2 border-[#0A4A1E] border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }
  if (!user) return <Navigate to="/login" state={{ from: location }} replace />;
  if (superAdminOnly && user.role !== "superadmin") return <AccessDenied />;
  if (adminOnly && !["admin", "superadmin"].includes(user.role)) return <AccessDenied />;
  if (roles && !roles.includes(user.role)) return <AccessDenied />;
  return children;
}
