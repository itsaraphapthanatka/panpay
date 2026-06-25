import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { adminApi } from "../api.js";

const baht = (n) => "฿" + Number(n).toLocaleString("th-TH", { minimumFractionDigits: 2 });
const fmt = (d) => (d ? new Date(d).toLocaleDateString("th-TH") : "—");

function EditModal({ merchant, onClose, onSaved, onError }) {
  const [feePercent, setFeePercent] = useState(String(merchant.fee_percent ?? 0));
  const [feeFixed, setFeeFixed] = useState(String(merchant.fee_fixed ?? 0));
  const [credit, setCredit] = useState(
    merchant.credit_per_transaction == null ? "" : String(merchant.credit_per_transaction)
  );
  const [busy, setBusy] = useState(false);

  async function save(e) {
    e.preventDefault();
    setBusy(true);
    try {
      const body = {
        fee_percent: Number(feePercent),
        fee_fixed: Number(feeFixed),
      };
      if (String(credit).trim() === "") {
        body.clear_credit_override = true;  // empty = use the global rate
      } else {
        body.credit_per_transaction = Number(credit);
      }
      await adminApi.updateMerchant(merchant.id, body);
      onSaved();
    } catch (e) {
      onError(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="modal-overlay" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <form className="modal-card" onSubmit={save}>
        <div className="modal-head">
          <h3>จัดการร้านค้า</h3>
          <button type="button" className="modal-close" onClick={onClose} aria-label="close">✕</button>
        </div>
        <p className="muted" style={{ marginTop: 0, fontSize: 13 }}>
          {merchant.business_name} · {merchant.email}
        </p>

        <strong style={{ fontSize: 14, display: "block", marginBottom: 8 }}>ค่าธรรมเนียม</strong>
        <div style={{ display: "flex", gap: 10 }}>
          <label className="field" style={{ flex: 1, marginBottom: 0 }}>
            <span className="lbl">เปอร์เซ็นต์ (%)</span>
            <input type="number" step="0.01" min="0" max="100" value={feePercent} onChange={(e) => setFeePercent(e.target.value)} />
          </label>
          <label className="field" style={{ flex: 1, marginBottom: 0 }}>
            <span className="lbl">คงที่/รายการ (฿)</span>
            <input type="number" step="0.01" min="0" value={feeFixed} onChange={(e) => setFeeFixed(e.target.value)} />
          </label>
        </div>

        <strong style={{ fontSize: 14, display: "block", marginTop: 18, marginBottom: 8 }}>เครดิต/รายการ</strong>
        <label className="field" style={{ marginBottom: 0 }}>
          <span className="lbl">ค่าบริการเฉพาะร้านนี้ (บาท/รายการ)</span>
          <input
            type="number"
            step="0.01"
            min="0"
            value={credit}
            onChange={(e) => setCredit(e.target.value)}
            placeholder="เว้นว่าง = ใช้ค่ากลางของระบบ"
          />
        </label>
        <span className="muted" style={{ fontSize: 12, marginTop: 6, display: "block" }}>
          เว้นว่างไว้เพื่อใช้ค่ากลางของระบบ
        </span>

        <div className="modal-actions">
          <button type="button" className="btn ghost" onClick={onClose}>ยกเลิก</button>
          <button className="btn" disabled={busy}>{busy ? "กำลังบันทึก…" : "บันทึก"}</button>
        </div>
      </form>
    </div>
  );
}

function ConfirmModal({ title, message, confirmLabel, danger, busy, onConfirm, onClose }) {
  return (
    <div className="modal-overlay" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal-card" style={{ maxWidth: 400 }}>
        <div className="modal-head">
          <h3>{title}</h3>
          <button type="button" className="modal-close" onClick={onClose} aria-label="close">✕</button>
        </div>
        <p style={{ marginTop: 0, color: "var(--text)" }}>{message}</p>
        <div className="modal-actions">
          <button type="button" className="btn ghost" onClick={onClose} disabled={busy}>ยกเลิก</button>
          <button type="button" className={`btn ${danger ? "danger" : ""}`} onClick={onConfirm} disabled={busy}>
            {busy ? "กำลังดำเนินการ…" : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function AdminMerchants() {
  const [merchants, setMerchants] = useState([]);
  const [q, setQ] = useState("");
  const [err, setErr] = useState("");
  const [busyId, setBusyId] = useState(null);
  const [editing, setEditing] = useState(null);
  const [confirming, setConfirming] = useState(null);

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

  async function doToggleSuspend() {
    const m = confirming;
    setBusyId(m.id);
    try {
      await adminApi.updateMerchant(m.id, { suspended: !m.suspended });
      setConfirming(null);
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
      <p className="page-sub">ดูทุกร้านค้า ปรับค่าธรรมเนียม/เครดิต และระงับ/ปลดระงับบัญชี</p>
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
              <th>เครดิต</th>
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
                <td>
                  {baht(m.balance)}
                  <br />
                  <span className="muted" style={{ fontSize: 12 }}>
                    {m.credit_per_transaction == null ? "rate กลาง" : `${baht(m.credit_per_transaction)}/รายการ`}
                  </span>
                </td>
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
                    <button className="btn ghost" style={{ padding: "4px 10px" }} onClick={() => setEditing(m)}>
                      จัดการ
                    </button>
                    <button
                      className={`btn ${m.suspended ? "" : "danger"}`}
                      style={{ padding: "4px 10px" }}
                      disabled={busyId === m.id}
                      onClick={() => setConfirming(m)}
                    >
                      {m.suspended ? "ปลดระงับ" : "ระงับ"}
                    </button>
                  </div>
                </td>
              </tr>
            ))}
            {merchants.length === 0 && (
              <tr>
                <td colSpan={8} className="muted" style={{ textAlign: "center", padding: 28 }}>
                  ไม่มีร้านค้า
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {editing && (
        <EditModal
          merchant={editing}
          onClose={() => setEditing(null)}
          onError={setErr}
          onSaved={() => { setEditing(null); load(); }}
        />
      )}

      {confirming && (
        <ConfirmModal
          title={confirming.suspended ? "ปลดระงับร้านค้า" : "ระงับร้านค้า"}
          message={
            confirming.suspended
              ? `ปลดระงับร้าน "${confirming.business_name}"? ร้านจะกลับมาเข้าระบบและรับชำระเงินได้ตามปกติ`
              : `ระงับร้าน "${confirming.business_name}"? ร้านจะเข้าระบบ/รับชำระเงินไม่ได้จนกว่าจะปลดระงับ`
          }
          confirmLabel={confirming.suspended ? "ปลดระงับ" : "ระงับ"}
          danger={!confirming.suspended}
          busy={busyId === confirming.id}
          onConfirm={doToggleSuspend}
          onClose={() => setConfirming(null)}
        />
      )}
    </div>
  );
}
