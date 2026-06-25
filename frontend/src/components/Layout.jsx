import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../auth.jsx";
import { setToken } from "../api.js";

const links = [
  { to: "/", label: "ภาพรวม", icon: "📊", end: true },
  { to: "/transactions", label: "รายการชำระเงิน", icon: "💳" },
  { to: "/members", label: "สมาชิก", icon: "👥" },
  { to: "/plans", label: "แผนสมาชิก", icon: "🗂️" },
  { to: "/coupons", label: "คูปอง", icon: "🎟️" },
  { to: "/settlements", label: "Settlement", icon: "🏦" },
  { to: "/topup", label: "เติมเงิน / เครดิต", icon: "💰" },
  { to: "/api-keys", label: "API Keys", icon: "🔑" },
  { to: "/audit", label: "บันทึกกิจกรรม", icon: "📜" },
  { to: "/settings", label: "ตั้งค่า", icon: "⚙️" },
];

export default function Layout() {
  const { merchant, logout } = useAuth();
  const impersonating = localStorage.getItem("panpay_impersonating");

  function exitImpersonation() {
    setToken(null);
    localStorage.removeItem("panpay_impersonating");
    window.location.assign("/admin");
  }

  function signOut() {
    localStorage.removeItem("panpay_impersonating");
    logout();
  }

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand-mark">
          <span className="brand-dot" />
          PanPay
        </div>
        {links.map((l) => (
          <NavLink key={l.to} to={l.to} end={l.end} className="nav-link">
            <span>{l.icon}</span> {l.label}
          </NavLink>
        ))}
        <div className="spacer" />
        <div style={{ padding: "8px 12px", fontSize: 13, color: "#94a3b8" }}>
          {merchant?.business_name}
          <br />
          <span style={{ fontSize: 12 }}>{merchant?.email}</span>
        </div>
        <button className="signout" onClick={signOut}>
          ออกจากระบบ
        </button>
      </aside>
      <main className="main">
        {impersonating && (
          <div
            className="notice"
            style={{
              display: "flex", justifyContent: "space-between", alignItems: "center",
              gap: 12, marginBottom: 16, background: "#fef3c7", borderColor: "#f59e0b", color: "#92400e",
            }}
          >
            <span>🔑 กำลังจัดการในนามร้านค้า <strong>{impersonating}</strong> (สิทธิ์ผู้ดูแลระบบ)</span>
            <button className="btn" style={{ padding: "4px 12px" }} onClick={exitImpersonation}>
              ← กลับไปหน้า Admin
            </button>
          </div>
        )}
        <Outlet />
      </main>
    </div>
  );
}
