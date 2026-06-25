import { useEffect, useState } from "react";
import { api } from "../api.js";
import { useDialog } from "../components/Dialog.jsx";

const baht = (n) => "฿" + Number(n).toLocaleString("th-TH", { minimumFractionDigits: 2 });
const intervalText = (u, c) => `ทุก ${c > 1 ? c + " " : ""}${{ day: "วัน", month: "เดือน", year: "ปี" }[u]}`;

export default function MemberPlans() {
  const [plans, setPlans] = useState([]);
  const [err, setErr] = useState("");
  const [form, setForm] = useState({ name: "", amount: "", interval_unit: "month", interval_count: 1, description: "" });
  const ui = useDialog();

  async function load() {
    try {
      setPlans(await api.listPlans());
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
      await api.createPlan({
        name: form.name,
        amount: parseFloat(form.amount),
        interval_unit: form.interval_unit,
        interval_count: parseInt(form.interval_count) || 1,
        description: form.description || null,
      });
      setForm({ name: "", amount: "", interval_unit: "month", interval_count: 1, description: "" });
      load();
    } catch (e) {
      setErr(e.message);
    }
  }

  async function deactivate(id) {
    try {
      await api.updatePlan(id, { active: false });
      load();
    } catch (e) {
      setErr(e.message);
    }
  }

  async function remove(id) {
    if (!(await ui.confirm({ title: "ลบแผนสมาชิก", message: "ลบแผนนี้?", confirmLabel: "ลบ", danger: true }))) return;
    try {
      await api.deletePlan(id);
      load();
    } catch (e) {
      setErr(e.message);
    }
  }

  return (
    <div>
      <h1 className="page-title">แผนสมาชิก</h1>
      <p className="page-sub">แพ็กเกจสมาชิกแบบจ่ายตามรอบของร้านคุณ — เพิ่ม/ปิดใช้งาน/ลบได้ที่นี่ (การรับสมัครสมาชิกจัดการโดยผู้ดูแลระบบ)</p>
      {err && <div className="error">{err}</div>}

      <div className="card">
        <table>
          <thead>
            <tr>
              <th>ชื่อแผน</th>
              <th>ราคา</th>
              <th>รอบบิล</th>
              <th>รายละเอียด</th>
              <th>สถานะ</th>
              <th style={{ textAlign: "right" }}>จัดการ</th>
            </tr>
          </thead>
          <tbody>
            {plans.map((p) => (
              <tr key={p.id}>
                <td>{p.name}</td>
                <td>{baht(p.amount)}</td>
                <td className="muted">{intervalText(p.interval_unit, p.interval_count)}</td>
                <td className="muted">{p.description || "—"}</td>
                <td>
                  {p.active ? (
                    <span className="badge paid">เปิดใช้งาน</span>
                  ) : (
                    <span className="badge canceled">ปิด</span>
                  )}
                </td>
                <td style={{ textAlign: "right" }}>
                  {p.active && (
                    <button className="btn ghost" style={{ padding: "4px 10px", marginRight: 6 }} onClick={() => deactivate(p.id)}>
                      ปิดใช้งาน
                    </button>
                  )}
                  <button className="btn danger" style={{ padding: "4px 10px" }} onClick={() => remove(p.id)}>
                    ลบ
                  </button>
                </td>
              </tr>
            ))}
            {plans.length === 0 && (
              <tr>
                <td colSpan={6} className="muted" style={{ textAlign: "center", padding: 28 }}>
                  ยังไม่มีแผนสมาชิก — เพิ่มแผนแรกด้านล่าง
                </td>
              </tr>
            )}
          </tbody>
        </table>

        <form onSubmit={add} style={{ display: "flex", gap: 8, alignItems: "flex-end", marginTop: 14, flexWrap: "wrap" }}>
          <label className="field" style={{ flex: 2, marginBottom: 0, minWidth: 140 }}>
            <span className="lbl">ชื่อแผน</span>
            <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Gold" required />
          </label>
          <label className="field" style={{ flex: 1, marginBottom: 0, minWidth: 90 }}>
            <span className="lbl">ราคา (฿)</span>
            <input type="number" step="0.01" min="0.01" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} required />
          </label>
          <label className="field" style={{ marginBottom: 0, width: 70 }}>
            <span className="lbl">ทุก</span>
            <input type="number" min="1" value={form.interval_count} onChange={(e) => setForm({ ...form, interval_count: e.target.value })} />
          </label>
          <label className="field" style={{ marginBottom: 0, width: 110 }}>
            <span className="lbl">หน่วย</span>
            <select value={form.interval_unit} onChange={(e) => setForm({ ...form, interval_unit: e.target.value })}>
              <option value="day">วัน</option>
              <option value="month">เดือน</option>
              <option value="year">ปี</option>
            </select>
          </label>
          <label className="field" style={{ flex: 2, marginBottom: 0, minWidth: 140 }}>
            <span className="lbl">รายละเอียด (ไม่บังคับ)</span>
            <input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
          </label>
          <button className="btn">เพิ่มแผน</button>
        </form>
      </div>
    </div>
  );
}
