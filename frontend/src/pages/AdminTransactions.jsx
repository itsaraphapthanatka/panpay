import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { adminApi } from "../api.js";
import StatusBadge from "../components/StatusBadge.jsx";

const baht = (n) => "฿" + Number(n).toLocaleString("th-TH", { minimumFractionDigits: 2 });
const fmt = (d) => (d ? new Date(d).toLocaleString("th-TH") : "—");

export default function AdminTransactions() {
  const [charges, setCharges] = useState([]);
  const [filter, setFilter] = useState("");
  const [err, setErr] = useState("");

  async function load() {
    try {
      setCharges(await adminApi.charges({ status: filter || undefined }));
    } catch (e) {
      setErr(e.message);
    }
  }
  useEffect(() => {
    load();
  }, [filter]);

  return (
    <div>
      <h1 className="page-title">รายการชำระเงิน (ทุกร้าน)</h1>
      <p className="page-sub">รายการชำระเงินทั้งหมดบนแพลตฟอร์ม</p>
      {err && <div className="error">{err}</div>}

      <div style={{ display: "flex", gap: 8, marginBottom: 14, flexWrap: "wrap" }}>
        {["", "paid", "pending", "refunded", "canceled", "expired"].map((s) => (
          <button key={s} className={`btn ${filter === s ? "" : "ghost"}`} onClick={() => setFilter(s)}>
            {{ "": "ทั้งหมด", paid: "ชำระแล้ว", pending: "รอชำระ", refunded: "คืนเงิน", canceled: "ยกเลิก", expired: "หมดอายุ" }[s]}
          </button>
        ))}
      </div>

      <div className="card">
        <table>
          <thead>
            <tr>
              <th>รหัสรายการ</th>
              <th>ร้านค้า</th>
              <th>รายละเอียด</th>
              <th>จำนวน</th>
              <th>สถานะ</th>
              <th>สร้างเมื่อ</th>
            </tr>
          </thead>
          <tbody>
            {charges.map((c) => (
              <tr key={c.id}>
                <td className="mono">{c.id.slice(0, 14)}…</td>
                <td><Link to={`/merchants/${c.merchant_id}`}>{c.business_name}</Link></td>
                <td>{c.description || "—"}</td>
                <td>{baht(c.amount)}</td>
                <td><StatusBadge status={c.status} /></td>
                <td className="muted">{fmt(c.created_at)}</td>
              </tr>
            ))}
            {charges.length === 0 && (
              <tr>
                <td colSpan={6} className="muted" style={{ textAlign: "center", padding: 28 }}>ไม่มีรายการ</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
