import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { adminApi } from "../api.js";
import StatusBadge from "../components/StatusBadge.jsx";

const baht = (n) => "฿" + Number(n).toLocaleString("th-TH", { minimumFractionDigits: 2 });
const fmt = (d) => (d ? new Date(d).toLocaleString("th-TH") : "—");

export default function AdminMerchantDetail() {
  const { id } = useParams();
  const [m, setM] = useState(null);
  const [charges, setCharges] = useState([]);
  const [settlements, setSettlements] = useState([]);
  const [err, setErr] = useState("");

  async function load() {
    try {
      const [merchant, ch, st] = await Promise.all([
        adminApi.merchant(id),
        adminApi.charges({ merchantId: id }),
        adminApi.settlements(id),
      ]);
      setM(merchant);
      setCharges(ch);
      setSettlements(st);
    } catch (e) {
      setErr(e.message);
    }
  }
  useEffect(() => {
    load();
  }, [id]);

  if (err) return <div className="error">{err}</div>;
  if (!m) return <div className="muted">กำลังโหลด…</div>;

  return (
    <div>
      <p style={{ marginBottom: 6 }}><Link to="/merchants">← ร้านค้าทั้งหมด</Link></p>
      <h1 className="page-title">{m.business_name}</h1>
      <p className="page-sub">
        {m.email} · PromptPay {m.promptpay_id || "—"} ·{" "}
        {m.suspended ? <span className="badge canceled">ถูกระงับ</span> : <span className="badge paid">ใช้งาน</span>}
      </p>

      <div style={{ display: "flex", gap: 14, flexWrap: "wrap", marginBottom: 18 }}>
        <div className="card" style={{ flex: 1, minWidth: 160 }}>
          <div className="muted" style={{ fontSize: 13 }}>ยอดชำระรวม</div>
          <div style={{ fontSize: 22, fontWeight: 700, color: "#22c55e" }}>{baht(m.paid_amount)}</div>
        </div>
        <div className="card" style={{ flex: 1, minWidth: 160 }}>
          <div className="muted" style={{ fontSize: 13 }}>รายการชำระแล้ว</div>
          <div style={{ fontSize: 22, fontWeight: 700 }}>{m.paid_count}</div>
        </div>
        <div className="card" style={{ flex: 1, minWidth: 160 }}>
          <div className="muted" style={{ fontSize: 13 }}>รอชำระ</div>
          <div style={{ fontSize: 22, fontWeight: 700 }}>{m.pending_count}</div>
        </div>
        <div className="card" style={{ flex: 1, minWidth: 160 }}>
          <div className="muted" style={{ fontSize: 13 }}>ค่าธรรมเนียม</div>
          <div style={{ fontSize: 22, fontWeight: 700 }}>{m.fee_percent}% + {baht(m.fee_fixed)}</div>
        </div>
      </div>

      <h3>รายการชำระเงินล่าสุด</h3>
      <div className="card" style={{ marginBottom: 18 }}>
        <table>
          <thead>
            <tr><th>รหัส</th><th>จำนวน</th><th>สถานะ</th><th>สร้างเมื่อ</th></tr>
          </thead>
          <tbody>
            {charges.map((c) => (
              <tr key={c.id}>
                <td className="mono">{c.id.slice(0, 16)}…</td>
                <td>{baht(c.amount)}</td>
                <td><StatusBadge status={c.status} /></td>
                <td className="muted">{fmt(c.created_at)}</td>
              </tr>
            ))}
            {charges.length === 0 && (
              <tr><td colSpan={4} className="muted" style={{ textAlign: "center", padding: 24 }}>ไม่มีรายการ</td></tr>
            )}
          </tbody>
        </table>
      </div>

      <h3>Settlements</h3>
      <div className="card">
        <table>
          <thead>
            <tr><th>รหัส</th><th>ยอดสุทธิ</th><th>ค่าธรรมเนียม</th><th>จำนวนรายการ</th><th>สถานะ</th><th>สร้างเมื่อ</th></tr>
          </thead>
          <tbody>
            {settlements.map((s) => (
              <tr key={s.id}>
                <td className="mono">{s.id.slice(0, 16)}…</td>
                <td>{baht(s.net_amount)}</td>
                <td>{baht(s.fee_amount)}</td>
                <td>{s.charge_count}</td>
                <td><span className={`badge ${s.status === "paid_out" ? "paid" : "pending"}`}>{s.status}</span></td>
                <td className="muted">{fmt(s.created_at)}</td>
              </tr>
            ))}
            {settlements.length === 0 && (
              <tr><td colSpan={6} className="muted" style={{ textAlign: "center", padding: 24 }}>ไม่มี settlement</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
