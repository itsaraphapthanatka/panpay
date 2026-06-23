import { Navigate, Route, Routes } from "react-router-dom";
import { useAdminAuth } from "./adminAuth.jsx";
import AdminLayout from "./components/AdminLayout.jsx";
import AdminLogin from "./pages/AdminLogin.jsx";
import AdminDashboard from "./pages/AdminDashboard.jsx";
import AdminMerchants from "./pages/AdminMerchants.jsx";
import AdminMerchantDetail from "./pages/AdminMerchantDetail.jsx";
import AdminTransactions from "./pages/AdminTransactions.jsx";
import AdminAuditLog from "./pages/AdminAuditLog.jsx";

function AdminProtected({ children }) {
  const { admin, loading } = useAdminAuth();
  if (loading) return <div style={{ padding: 40 }}>Loading…</div>;
  if (!admin) return <Navigate to="/login" replace />;
  return children;
}

export default function AdminApp() {
  const { admin } = useAdminAuth();
  return (
    <Routes>
      <Route path="/login" element={admin ? <Navigate to="/" replace /> : <AdminLogin />} />
      <Route
        path="/"
        element={
          <AdminProtected>
            <AdminLayout />
          </AdminProtected>
        }
      >
        <Route index element={<AdminDashboard />} />
        <Route path="merchants" element={<AdminMerchants />} />
        <Route path="merchants/:id" element={<AdminMerchantDetail />} />
        <Route path="transactions" element={<AdminTransactions />} />
        <Route path="audit" element={<AdminAuditLog />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
