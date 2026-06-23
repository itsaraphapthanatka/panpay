import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth.jsx";
import Layout from "./components/Layout.jsx";
import Login from "./pages/Login.jsx";
import Register from "./pages/Register.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import Transactions from "./pages/Transactions.jsx";
import ApiKeys from "./pages/ApiKeys.jsx";
import Settings from "./pages/Settings.jsx";
import AuditLog from "./pages/AuditLog.jsx";
import Settlements from "./pages/Settlements.jsx";
import Members from "./pages/Members.jsx";
import Portal from "./pages/Portal.jsx";
import Checkout from "./pages/Checkout.jsx";

function Protected({ children }) {
  const { merchant, loading } = useAuth();
  if (loading) return <div style={{ padding: 40 }}>Loading…</div>;
  if (!merchant) return <Navigate to="/login" replace />;
  return children;
}

export default function App() {
  const { merchant } = useAuth();
  return (
    <Routes>
      {/* Public pages */}
      <Route path="/pay/:chargeId" element={<Checkout />} />
      <Route path="/m/:token" element={<Portal />} />

      <Route path="/login" element={merchant ? <Navigate to="/" replace /> : <Login />} />
      <Route path="/register" element={merchant ? <Navigate to="/" replace /> : <Register />} />

      <Route
        path="/"
        element={
          <Protected>
            <Layout />
          </Protected>
        }
      >
        <Route index element={<Dashboard />} />
        <Route path="transactions" element={<Transactions />} />
        <Route path="api-keys" element={<ApiKeys />} />
        <Route path="settlements" element={<Settlements />} />
        <Route path="members" element={<Members />} />
        <Route path="audit" element={<AuditLog />} />
        <Route path="settings" element={<Settings />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
