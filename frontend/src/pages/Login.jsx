import { useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../auth.jsx";

export default function Login() {
  const { login } = useAuth();
  const [email, setEmail] = useState("demo@panpay.io");
  const [password, setPassword] = useState("demo1234");
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
          <span className="brand-dot" /> PanPay
        </div>
        <h2 style={{ margin: "0 0 4px" }}>เข้าสู่ระบบร้านค้า</h2>
        <p className="muted" style={{ marginTop: 0 }}>จัดการการรับชำระเงินของคุณ</p>
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
        <p className="muted" style={{ textAlign: "center", marginBottom: 0, marginTop: 16 }}>
          ยังไม่มีบัญชี? <Link to="/register">สมัครร้านค้า</Link>
        </p>
      </form>
    </div>
  );
}
