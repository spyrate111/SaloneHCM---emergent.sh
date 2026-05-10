import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider } from "./context/AuthContext";
import ProtectedRoute from "./components/ProtectedRoute";
import Layout from "./components/Layout";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import Employees from "./pages/Employees";
import EmployeeDetail from "./pages/EmployeeDetail";
import Payroll from "./pages/Payroll";
import Compliance from "./pages/Compliance";
import Leave from "./pages/Leave";
import Attendance from "./pages/Attendance";
import Assistant from "./pages/Assistant";
import Settings from "./pages/Settings";
import SelfService from "./pages/SelfService";
import AuditLog from "./pages/AuditLog";
import Benefits from "./pages/Benefits";
import Talent from "./pages/Talent";
import Analytics from "./pages/Analytics";
import Simulator from "./pages/Simulator";
import Team from "./pages/Team";
import { Toaster } from "./components/ui/sonner";

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route element={<ProtectedRoute><Layout /></ProtectedRoute>}>
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/employees" element={<ProtectedRoute adminOnly><Employees /></ProtectedRoute>} />
            <Route path="/employees/:id" element={<ProtectedRoute adminOnly><EmployeeDetail /></ProtectedRoute>} />
            <Route path="/payroll" element={<ProtectedRoute adminOnly><Payroll /></ProtectedRoute>} />
            <Route path="/simulator" element={<ProtectedRoute adminOnly><Simulator /></ProtectedRoute>} />
            <Route path="/compliance" element={<ProtectedRoute adminOnly><Compliance /></ProtectedRoute>} />
            <Route path="/leave" element={<Leave />} />
            <Route path="/attendance" element={<Attendance />} />
            <Route path="/benefits" element={<Benefits />} />
            <Route path="/talent" element={<Talent />} />
            <Route path="/analytics" element={<ProtectedRoute adminOnly><Analytics /></ProtectedRoute>} />
            <Route path="/assistant" element={<Assistant />} />
            <Route path="/self-service" element={<SelfService />} />
            <Route path="/audit" element={<ProtectedRoute adminOnly><AuditLog /></ProtectedRoute>} />
            <Route path="/team" element={<Team />} />
            <Route path="/team/:eid" element={<ProtectedRoute adminOnly><Team /></ProtectedRoute>} />
            <Route path="/settings" element={<ProtectedRoute adminOnly><Settings /></ProtectedRoute>} />
          </Route>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
        <Toaster />
      </BrowserRouter>
    </AuthProvider>
  );
}
