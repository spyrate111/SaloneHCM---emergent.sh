import { useEffect } from "react";
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
import Documents from "./pages/Documents";
import Users from "./pages/Users";
import Companies from "./pages/Companies";
import SmsLogs from "./pages/SmsLogs";
import Schedules from "./pages/Schedules";
import Ministry from "./pages/Ministry";
import Transparency from "./pages/Transparency";
import PublicCareers from "./pages/PublicCareers";
import Performance from "./pages/Performance";
import Verify from "./pages/Verify";
import CivilService from "./pages/CivilService";
import Establishment from "./pages/Establishment";
import Loans from "./pages/Loans";
import Billing from "./pages/Billing";
import SectorPresets from "./pages/SectorPresets";
import Promotion from "./pages/Promotion";
import Vouchers from "./pages/Vouchers";
import LandingPage from "./marketing/LandingPage";
import PricingPage from "./marketing/PricingPage";
import DemoPage from "./marketing/DemoPage";
import TourPage from "./marketing/TourPage";
import VideosPage from "./marketing/VideosPage";
import AdminVideos from "./pages/admin/Videos";
import { Toaster } from "./components/ui/sonner";

export default function App() {
  useEffect(() => {
    if ("serviceWorker" in navigator) {
      navigator.serviceWorker.register("/sw.js").catch((e) => console.warn("SW registration failed", e));
    }
  }, []);
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/pricing" element={<PricingPage />} />
          <Route path="/demo" element={<DemoPage />} />
          <Route path="/tour" element={<TourPage />} />
          <Route path="/videos" element={<VideosPage />} />
          <Route path="/login" element={<Login />} />
          <Route path="/transparency/:slug" element={<Transparency />} />
          <Route path="/careers/:slug" element={<PublicCareers />} />
          <Route path="/verify/:cid" element={<Verify />} />
          <Route element={<ProtectedRoute><Layout /></ProtectedRoute>}>
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/employees" element={<ProtectedRoute adminOnly><Employees /></ProtectedRoute>} />
            <Route path="/employees/:id" element={<ProtectedRoute adminOnly><EmployeeDetail /></ProtectedRoute>} />
            <Route path="/payroll" element={<ProtectedRoute adminOnly><Payroll /></ProtectedRoute>} />
            <Route path="/schedules" element={<ProtectedRoute adminOnly><Schedules /></ProtectedRoute>} />
            <Route path="/vouchers" element={<Vouchers />} />
            <Route path="/simulator" element={<ProtectedRoute adminOnly><Simulator /></ProtectedRoute>} />
            <Route path="/compliance" element={<ProtectedRoute adminOnly><Compliance /></ProtectedRoute>} />
            <Route path="/leave" element={<Leave />} />
            <Route path="/attendance" element={<Attendance />} />
            <Route path="/benefits" element={<Benefits />} />
            <Route path="/talent" element={<Talent />} />
            <Route path="/performance" element={<Performance />} />
            <Route path="/civil-service" element={<CivilService />} />
            <Route path="/establishment" element={<ProtectedRoute adminOnly><Establishment /></ProtectedRoute>} />
            <Route path="/loans" element={<Loans />} />
            <Route path="/billing" element={<ProtectedRoute adminOnly><Billing /></ProtectedRoute>} />
            <Route path="/sector-presets" element={<ProtectedRoute adminOnly><SectorPresets /></ProtectedRoute>} />
            <Route path="/promotion" element={<ProtectedRoute adminOnly><Promotion /></ProtectedRoute>} />
            <Route path="/analytics" element={<ProtectedRoute adminOnly><Analytics /></ProtectedRoute>} />
            <Route path="/assistant" element={<Assistant />} />
            <Route path="/self-service" element={<SelfService />} />
            <Route path="/audit" element={<ProtectedRoute adminOnly><AuditLog /></ProtectedRoute>} />
            <Route path="/team" element={<Team />} />
            <Route path="/team/:eid" element={<ProtectedRoute adminOnly><Team /></ProtectedRoute>} />
            <Route path="/documents" element={<Documents />} />
            <Route path="/users" element={<ProtectedRoute adminOnly><Users /></ProtectedRoute>} />
            <Route path="/sms-logs" element={<ProtectedRoute adminOnly><SmsLogs /></ProtectedRoute>} />
            <Route path="/ministry" element={<ProtectedRoute adminOnly><Ministry /></ProtectedRoute>} />
            <Route path="/companies" element={<ProtectedRoute superAdminOnly><Companies /></ProtectedRoute>} />
            <Route path="/admin/videos" element={<ProtectedRoute superAdminOnly><AdminVideos /></ProtectedRoute>} />
            <Route path="/settings" element={<ProtectedRoute adminOnly><Settings /></ProtectedRoute>} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
        <Toaster />
      </BrowserRouter>
    </AuthProvider>
  );
}
