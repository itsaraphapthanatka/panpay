import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, API_URL } from "../api.js";
import StatusBadge from "../components/StatusBadge.jsx";

// Load panpay.js (the embeddable popup script) on demand, then resolve.
function loadPanpayScript() {
  return new Promise((resolve, reject) => {
    if (window.PanPay) return resolve(window.PanPay);
    const s = document.createElement("script");
    s.src = `${API_URL}/panpay.js`;
    s.onload = () => resolve(window.PanPay);
    s.onerror = () => reject(new Error("โหลด panpay.js ไม่สำเร็จ"));
    document.head.appendChild(s);
  });
}

const baht = (n) => "฿" + Number(n).toLocaleString("th-TH", { minimumFractionDigits: 2 });

function BarChart({ series }) {
  const max = Math.max(1, ...series.map((d) => d.amount));
  return (
    <div style={{ display: "flex", alignItems: "flex-end", gap: 6, height: 160, marginTop: 8 }}>
      {series.map((d) => (
        <div key={d.date} title={`${d.date}: ${baht(d.amount)} (${d.count})`} style={{ flex: 1, display: "flex", flexDirection: "column", justifyContent: "flex-end", alignItems: "center", gap: 6 }}>
          <div
            style={{
              width: "100%",
              height: `${(d.amount / max) * 130}px`,
              minHeight: d.amount > 0 ? 4 : 0,
              background: "linear-gradient(180deg,#6366f1,#4f46e5)",
              borderRadius: 6,
            }}
          />
          <span style={{ fontSize: 10, color: "var(--muted)" }}>{d.date.slice(5)}</span>
        </div>
      ))}
    </div>
  );
}

export default function Dashboard() {
  const [stats, setStats] = useState(null);
  const [charges, setCharges] = useState([]);
  const [err, setErr] = useState("");

  // create-payment form
  const [amount, setAmount] = useState("");
  const [desc, setDesc] = useState("");
  const [accountId, setAccountId] = useState("");
  const [accounts, setAccounts] = useState([]);
  const [created, setCreated] = useState(null);
  const [busy, setBusy] = useState(false);

  async function load() {
    try {
      const [s, c, a] = await Promise.all([api.stats(14), api.charges(), api.listAccounts()]);
      setStats(s);
      setCharges(c.slice(0, 6));
      setAccounts(a);
    } catch (e) {
      setErr(e.message);
    }
  }
  useEffect(() => {
    load();
  }, []);

  async function createPayment(e) {
    e.preventDefault();
    setErr("");
    setBusy(true);
    try {
      const charge = await api.createCharge({
        amount: parseFloat(amount),
        description: desc || null,
        account_id: accountId || null,
      });
      setCreated(charge);
      setAmount("");
      setDesc("");
      load();
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <h1 className="page-title">ภาพรวม</h1>
      <p className="page-sub">สรุปยอดขายและการชำระเงินล่าสุด</p>
      {err && <div className="error">{err}</div>}

      <div className="grid cols-4">
        <div className="card">
          <div className="stat-label">ยอดรับชำระ (14 วัน)</div>
          <div className="stat-value green">{baht(stats?.total_paid_amount ?? 0)}</div>
        </div>
        <div className="card">
          <div className="stat-label">รายการสำเร็จ</div>
          <div className="stat-value">{stats?.paid_count ?? 0}</div>
        </div>
        <div className="card">
          <div className="stat-label">รอชำระ</div>
          <div className="stat-value">{stats?.pending_count ?? 0}</div>
        </div>
        <div className="card">
          <div className="stat-label">ยอดวันนี้</div>
          <div className="stat-value">{baht(stats?.today_amount ?? 0)}</div>
        </div>
      </div>

      <div className="grid cols-2" style={{ marginTop: 16 }}>
        <div className="card">
          <strong>ยอดขายรายวัน</strong>
          {stats && <BarChart series={stats.series} />}
        </div>

        <div className="card">
          <strong>สร้างลิงก์รับชำระเงิน</strong>
          {created ? (
            <div style={{ marginTop: 12 }}>
              <div className="notice">สร้างรายการสำเร็จ — ส่งลิงก์นี้ให้ลูกค้า</div>
              <input readOnly value={created.checkout_url} onFocus={(e) => e.target.select()} className="mono" />
              <div style={{ display: "flex", gap: 8, marginTop: 10, flexWrap: "wrap" }}>
                <a className="btn" href={created.checkout_url} target="_blank" rel="noreferrer">
                  เปิดหน้าชำระเงิน
                </a>
                <button
                  className="btn ghost"
                  onClick={async () => {
                    try {
                      const PanPay = await loadPanpayScript();
                      PanPay.checkout({
                        chargeId: created.id,
                        onSuccess: () => load(),
                      });
                    } catch (e) {
                      setErr(e.message);
                    }
                  }}
                >
                  จ่ายแบบ popup (ฝังในเว็บ)
                </button>
                <button className="btn ghost" onClick={() => setCreated(null)}>
                  สร้างใหม่
                </button>
              </div>
            </div>
          ) : (
            <form onSubmit={createPayment} style={{ marginTop: 12 }}>
              <label className="field">
                <span className="lbl">จำนวนเงิน (บาท)</span>
                <input type="number" step="0.01" min="0.01" value={amount} onChange={(e) => setAmount(e.target.value)} required />
              </label>
              <label className="field">
                <span className="lbl">รายละเอียด (ไม่บังคับ)</span>
                <input value={desc} onChange={(e) => setDesc(e.target.value)} placeholder="เช่น ค่าสินค้า #1234" />
              </label>
              {accounts.length > 0 && (
                <label className="field">
                  <span className="lbl">บัญชีรับเงิน</span>
                  <select value={accountId} onChange={(e) => setAccountId(e.target.value)}>
                    <option value="">ค่าเริ่มต้น</option>
                    {accounts.map((a) => (
                      <option key={a.id} value={a.id}>
                        {a.name} ({a.promptpay_id}){a.is_default ? " · ค่าเริ่มต้น" : ""}
                      </option>
                    ))}
                  </select>
                </label>
              )}
              <button className="btn block" disabled={busy}>
                {busy ? "กำลังสร้าง…" : "สร้างลิงก์ + QR"}
              </button>
            </form>
          )}
        </div>
      </div>

      <div className="card" style={{ marginTop: 16 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <strong>รายการล่าสุด</strong>
          <Link to="/transactions">ดูทั้งหมด →</Link>
        </div>
        <table style={{ marginTop: 10 }}>
          <thead>
            <tr>
              <th>รหัส</th>
              <th>รายละเอียด</th>
              <th>จำนวน</th>
              <th>สถานะ</th>
            </tr>
          </thead>
          <tbody>
            {charges.map((c) => (
              <tr key={c.id}>
                <td className="mono">{c.id.slice(0, 14)}…</td>
                <td>{c.description || "—"}</td>
                <td>{baht(c.amount)}</td>
                <td>
                  <StatusBadge status={c.status} />
                </td>
              </tr>
            ))}
            {charges.length === 0 && (
              <tr>
                <td colSpan={4} className="muted" style={{ textAlign: "center", padding: 24 }}>
                  ยังไม่มีรายการ
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
