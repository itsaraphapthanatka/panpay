import { useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../auth.jsx";

export default function Register() {
  const { register } = useAuth();
  const [form, setForm] = useState({
    business_name: "",
    email: "",
    password: "",
    promptpay_id: "",
  });
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  async function submit(e) {
    e.preventDefault();
    setErr("");
    setBusy(true);
    try {
      await register({ ...form, promptpay_id: form.promptpay_id || null });
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
        <h2 style={{ margin: "0 0 4px" }}>สมัครร้านค้า</h2>
        <p className="muted" style={{ marginTop: 0 }}>เริ่มรับชำระเงินผ่าน PromptPay</p>
        {err && <div className="error">{err}</div>}
        <label className="field">
          <span className="lbl">ชื่อร้านค้า</span>
          <input value={form.business_name} onChange={set("business_name")} required />
        </label>
        <label className="field">
          <span className="lbl">อีเมล</span>
          <input value={form.email} onChange={set("email")} type="email" required />
        </label>
        <label className="field">
          <span className="lbl">รหัสผ่าน (อย่างน้อย 6 ตัว)</span>
          <input value={form.password} onChange={set("password")} type="password" minLength={6} required />
        </label>
        <label className="field">
          <span className="lbl">PromptPay ID (เบอร์มือถือ / เลขบัตรปชช.) — ตั้งภายหลังได้</span>
          <input value={form.promptpay_id} onChange={set("promptpay_id")} placeholder="0812345678" />
        </label>
        <button className="btn block" disabled={busy}>
          {busy ? "กำลังสมัคร…" : "สมัครและเริ่มใช้งาน"}
        </button>
        <p className="muted" style={{ textAlign: "center", marginBottom: 0, marginTop: 16 }}>
          มีบัญชีแล้ว? <Link to="/login">เข้าสู่ระบบ</Link>
        </p>
      </form>
    </div>
  );
}
