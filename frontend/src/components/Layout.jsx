import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../auth.jsx";

const links = [
  { to: "/", label: "ภาพรวม", icon: "📊", end: true },
  { to: "/transactions", label: "รายการชำระเงิน", icon: "💳" },
  { to: "/members", label: "สมาชิก", icon: "👥" },
  { to: "/settlements", label: "Settlement", icon: "🏦" },
  { to: "/api-keys", label: "API Keys", icon: "🔑" },
  { to: "/audit", label: "บันทึกกิจกรรม", icon: "📜" },
  { to: "/settings", label: "ตั้งค่า", icon: "⚙️" },
];

export default function Layout() {
  const { merchant, logout } = useAuth();
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
        <button className="signout" onClick={logout}>
          ออกจากระบบ
        </button>
      </aside>
      <main className="main">
        <Outlet />
      </main>
    </div>
  );
}
