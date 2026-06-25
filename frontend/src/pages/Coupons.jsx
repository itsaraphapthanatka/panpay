import { useEffect, useState } from "react";
import { api } from "../api.js";
import { useDialog } from "../components/Dialog.jsx";

const baht = (n) => "฿" + Number(n).toLocaleString("th-TH", { minimumFractionDigits: 2 });

export default function Coupons() {
  const [coupons, setCoupons] = useState([]);
  const [err, setErr] = useState("");
  const [form, setForm] = useState({ code: "", discount_type: "percent", value: "", duration: "once" });
  const ui = useDialog();

  async function load() {
    try {
      setCoupons(await api.listCoupons());
    } catch (e) {
      setErr(e.message);
    }
  }
  useEffect(() => {
    load();
  }, []);

  async function add(e) {
    e.preventDefault();
    setErr("");
    try {
      await api.createCoupon({
        code: form.code,
        discount_type: form.discount_type,
        value: parseFloat(form.value),
        duration: form.duration,
      });
      setForm({ code: "", discount_type: "percent", value: "", duration: "once" });
      load();
    } catch (e) {
      setErr(e.message);
    }
  }

  async function disable(id) {
    if (!(await ui.confirm({ title: "ปิดคูปอง", message: "ปิดคูปองนี้?", confirmLabel: "ปิดคูปอง", danger: true }))) return;
    try {
      await api.deleteCoupon(id);
      load();
    } catch (e) {
      setErr(e.message);
    }
  }

  return (
    <div>
      <h1 className="page-title">คูปอง / ส่วนลด</h1>
      <p className="page-sub">โค้ดส่วนลดสำหรับใช้ตอนรับสมัครสมาชิก (ลดครั้งแรก หรือ ทุกบิล)</p>
      {err && <div className="error">{err}</div>}

      <div className="card">
        <table>
          <thead>
            <tr>
              <th>โค้ด</th>
              <th>ส่วนลด</th>
              <th>ใช้กับ</th>
              <th>ใช้ไปแล้ว</th>
              <th>สถานะ</th>
              <th style={{ textAlign: "right" }}>จัดการ</th>
            </tr>
          </thead>
          <tbody>
            {coupons.map((c) => (
              <tr key={c.id}>
                <td className="mono">{c.code}</td>
                <td>{c.discount_type === "percent" ? `${c.value}%` : baht(c.value)}</td>
                <td className="muted">{c.duration === "forever" ? "ทุกบิล" : "ครั้งแรก"}</td>
                <td className="muted">{c.times_redeemed}{c.max_redemptions ? `/${c.max_redemptions}` : ""}</td>
                <td>
                  {c.active ? (
                    <span className="badge paid">เปิดใช้งาน</span>
                  ) : (
                    <span className="badge canceled">ปิด</span>
                  )}
                </td>
                <td style={{ textAlign: "right" }}>
                  {c.active && (
                    <button className="btn danger" style={{ padding: "4px 10px" }} onClick={() => disable(c.id)}>
                      ปิด
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {coupons.length === 0 && (
              <tr>
                <td colSpan={6} className="muted" style={{ textAlign: "center", padding: 28 }}>
                  ยังไม่มีคูปอง — เพิ่มคูปองแรกด้านล่าง
                </td>
              </tr>
            )}
          </tbody>
        </table>

        <form onSubmit={add} style={{ display: "flex", gap: 8, alignItems: "flex-end", marginTop: 14, flexWrap: "wrap" }}>
          <label className="field" style={{ marginBottom: 0, width: 140 }}>
            <span className="lbl">โค้ด</span>
            <input value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} placeholder="SAVE20" required />
          </label>
          <label className="field" style={{ marginBottom: 0, width: 120 }}>
            <span className="lbl">ประเภท</span>
            <select value={form.discount_type} onChange={(e) => setForm({ ...form, discount_type: e.target.value })}>
              <option value="percent">เปอร์เซ็นต์</option>
              <option value="fixed">บาท</option>
            </select>
          </label>
          <label className="field" style={{ marginBottom: 0, width: 100 }}>
            <span className="lbl">ค่า</span>
            <input type="number" step="0.01" min="0.01" value={form.value} onChange={(e) => setForm({ ...form, value: e.target.value })} required />
          </label>
          <label className="field" style={{ marginBottom: 0, width: 120 }}>
            <span className="lbl">ใช้</span>
            <select value={form.duration} onChange={(e) => setForm({ ...form, duration: e.target.value })}>
              <option value="once">ครั้งแรก</option>
              <option value="forever">ทุกบิล</option>
            </select>
          </label>
          <button className="btn">เพิ่มคูปอง</button>
        </form>
      </div>
    </div>
  );
}
