import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { adminApi } from "../api.js";

const baht = (n) => "฿" + Number(n).toLocaleString("th-TH", { minimumFractionDigits: 2 });
const fmt = (d) => (d ? new Date(d).toLocaleDateString("th-TH") : "—");

export default function AdminMerchants() {
  const [merchants, setMerchants] = useState([]);
  const [q, setQ] = useState("");
  const [err, setErr] = useState("");
  const [busyId, setBusyId] = useState(null);

  async function load() {
    try {
      setMerchants(await adminApi.merchants(q || undefined));
    } catch (e) {
      setErr(e.message);
    }
  }
  useEffect(() => {
    const t = setTimeout(load, 250);
    return () => clearTimeout(t);
  }, [q]);

  async function toggleSuspend(m) {
    const verb = m.suspended ? "ปลดระงับ" : "ระงับ";
    if (!confirm(`${verb}ร้าน "${m.business_name}"?`)) return;
    setBusyId(m.id);
    try {
      await adminApi.updateMerchant(m.id, { suspended: !m.suspended });
      load();
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusyId(null);
    }
  }

  async function editFee(m) {
    const fp = prompt(`ค่าธรรมเนียม % สำหรับ "${m.business_name}"`, m.fee_percent);
    if (fp === null) return;
    const ff = prompt(`ค่าธรรมเนียมคงที่ (บาท) สำหรับ "${m.business_name}"`, m.fee_fixed);
    if (ff === null) return;
    setBusyId(m.id);
    try {
      await adminApi.updateMerchant(m.id, { fee_percent: Number(fp), fee_fixed: Number(ff) });
      load();
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div>
      <h1 className="page-title">ร้านค้า</h1>
      <p className="page-sub">ดูทุกร้านค้า ปรับค่าธรรมเนียม และระงับ/ปลดระงับบัญชี</p>
      {err && <div className="error">{err}</div>}

      <div style={{ marginBottom: 14 }}>
        <input
          placeholder="ค้นหาอีเมลหรือชื่อร้าน…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          style={{ maxWidth: 320 }}
        />
      </div>

      <div className="card">
        <table>
          <thead>
            <tr>
              <th>ร้านค้า</th>
              <th>ค่าธรรมเนียม</th>
              <th>รายการ</th>
              <th>ยอดชำระ</th>
              <th>สถานะ</th>
              <th>สมัครเมื่อ</th>
              <th>จัดการ</th>
            </tr>
          </thead>
          <tbody>
            {merchants.map((m) => (
              <tr key={m.id}>
                <td>
                  <Link to={`/merchants/${m.id}`}>{m.business_name}</Link>
                  <br />
                  <span className="muted" style={{ fontSize: 12 }}>{m.email}</span>
                </td>
                <td>{m.fee_percent}% + {baht(m.fee_fixed)}</td>
                <td>{m.charge_count} <span className="muted">({m.pending_count} รอ)</span></td>
                <td>{baht(m.paid_amount)} <span className="muted">({m.paid_count})</span></td>
                <td>
                  {m.suspended ? (
                    <span className="badge canceled">ถูกระงับ</span>
                  ) : (
                    <span className="badge paid">ใช้งาน</span>
                  )}
                </td>
                <td className="muted">{fmt(m.created_at)}</td>
                <td>
                  <div style={{ display: "flex", gap: 6 }}>
                    <button className="btn ghost" style={{ padding: "4px 10px" }} disabled={busyId === m.id} onClick={() => editFee(m)}>
                      ค่าธรรมเนียม
                    </button>
                    <button
                      className={`btn ${m.suspended ? "" : "danger"}`}
                      style={{ padding: "4px 10px" }}
                      disabled={busyId === m.id}
                      onClick={() => toggleSuspend(m)}
                    >
                      {m.suspended ? "ปลดระงับ" : "ระงับ"}
                    </button>
                  </div>
                </td>
              </tr>
            ))}
            {merchants.length === 0 && (
              <tr>
                <td colSpan={7} className="muted" style={{ textAlign: "center", padding: 28 }}>
                  ไม่มีร้านค้า
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
