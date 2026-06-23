import { useState } from "react";
import { useAdminAuth } from "../adminAuth.jsx";

export default function AdminLogin() {
  const { login } = useAdminAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setErr("");
    setBusy(true);
    try {
      await login(email, password);
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-wrap">
      <form className="auth-card" onSubmit={submit}>
        <div className="brand-mark" style={{ marginBottom: 22 }}>
          <span className="brand-dot" style={{ background: "#f59e0b" }} /> PanPay
          <span style={{ fontSize: 12, color: "#f59e0b", marginLeft: 4 }}>ADMIN</span>
        </div>
        <h2 style={{ margin: "0 0 4px" }}>เข้าสู่ระบบผู้ดูแล</h2>
        <p className="muted" style={{ marginTop: 0 }}>จัดการแพลตฟอร์มและร้านค้าทั้งหมด</p>
        {err && <div className="error">{err}</div>}
        <label className="field">
          <span className="lbl">อีเมล</span>
          <input value={email} onChange={(e) => setEmail(e.target.value)} type="email" required />
        </label>
        <label className="field">
          <span className="lbl">รหัสผ่าน</span>
          <input value={password} onChange={(e) => setPassword(e.target.value)} type="password" required />
        </label>
        <button className="btn block" disabled={busy}>
          {busy ? "กำลังเข้าสู่ระบบ…" : "เข้าสู่ระบบ"}
        </button>
      </form>
    </div>
  );
}
