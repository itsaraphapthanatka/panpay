import { NavLink, Outlet } from "react-router-dom";
import { useAdminAuth } from "../adminAuth.jsx";
import Logo from "./Logo.jsx";

const links = [
  { to: "/", label: "ภาพรวมระบบ", icon: "📊", end: true },
  { to: "/merchants", label: "ร้านค้า", icon: "🏪" },
  { to: "/transactions", label: "รายการชำระเงิน", icon: "💳" },
  { to: "/audit", label: "บันทึกกิจกรรม", icon: "📜" },
  { to: "/settings", label: "ตั้งค่า", icon: "⚙️" },
];

export default function AdminLayout() {
  const { admin, logout } = useAdminAuth();
  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand-mark">
          <Logo light height={24} />
          <span style={{ fontSize: 12, color: "#f59e0b", marginLeft: 8, fontWeight: 800 }}>ADMIN</span>
        </div>
        {links.map((l) => (
          <NavLink key={l.to} to={l.to} end={l.end} className="nav-link">
            <span>{l.icon}</span> {l.label}
          </NavLink>
        ))}
        <div className="spacer" />
        <div style={{ padding: "8px 12px", fontSize: 13, color: "#94a3b8" }}>
          {admin?.name}
          <br />
          <span style={{ fontSize: 12 }}>{admin?.email}</span>
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
