import { useEffect, useState } from "react";
import { adminApi } from "../api.js";

const baht = (n) => "฿" + Number(n).toLocaleString("th-TH", { minimumFractionDigits: 2 });

function Stat({ label, value, accent }) {
  return (
    <div className="card" style={{ flex: 1, minWidth: 180 }}>
      <div className="muted" style={{ fontSize: 13 }}>{label}</div>
      <div style={{ fontSize: 26, fontWeight: 700, marginTop: 6, color: accent }}>{value}</div>
    </div>
  );
}

function PlatformSettings({ onError }) {
  const [s, setS] = useState(null);
  const [pp, setPp] = useState("");
  const [rate, setRate] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");

  async function refresh() {
    try {
      const v = await adminApi.getSettings();
      setS(v);
      setPp(v.platform_promptpay || "");
      setRate(String(v.credit_per_transaction));
    } catch (e) { onError(e.message); }
  }
  useEffect(() => { refresh(); }, []);

  async function patch(body, okMsg) {
    setBusy(true);
    setMsg("");
    try {
      const v = await adminApi.updateSettings(body);
      setS(v);
      setPp(v.platform_promptpay || "");
      setRate(String(v.credit_per_transaction));
      if (okMsg) setMsg(okMsg);
    } catch (e) { onError(e.message); } finally { setBusy(false); }
  }

  if (!s) return null;
  const ingestUrl = `${window.location.origin}/api/topup/incoming`;

  return (
    <div className="card" style={{ marginBottom: 14 }}>
      <strong>ตั้งค่าแพลตฟอร์ม</strong>
      {msg && <div className="notice" style={{ marginTop: 8 }}>{msg}</div>}

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 16, marginTop: 12, flexWrap: "wrap" }}>
        <div className="muted" style={{ fontSize: 13 }}>
          ตรวจเงินเข้าอัตโนมัติ (Bank Auto-check){s.auto_bank_check === false && " — ปิดอยู่"}
        </div>
        <button className={`btn ${s.auto_bank_check ? "danger" : ""}`} disabled={busy}
                onClick={() => patch({ auto_bank_check: !s.auto_bank_check })} style={{ minWidth: 100 }}>
          {s.auto_bank_check ? "ปิดใช้งาน" : "เปิดใช้งาน"}
        </button>
      </div>

      <div className="grid cols-2" style={{ marginTop: 14, gap: 12 }}>
        <div>
          <label className="field" style={{ marginBottom: 6 }}>
            <span className="lbl">PromptPay แพลตฟอร์ม (บัญชีรับเงินเติมเครดิตของร้านค้า)</span>
            <input value={pp} onChange={(e) => setPp(e.target.value)} placeholder="0812345678 / เลขนิติบุคคล" />
          </label>
          <button className="btn ghost" disabled={busy} onClick={() => patch({ platform_promptpay: pp }, "บันทึก PromptPay แล้ว")}>บันทึก</button>
        </div>
        <div>
          <label className="field" style={{ marginBottom: 6 }}>
            <span className="lbl">ค่าบริการต่อรายการ (เครดิตที่หัก/transaction, บาท)</span>
            <input type="number" step="0.01" min="0" value={rate} onChange={(e) => setRate(e.target.value)} />
          </label>
          <button className="btn ghost" disabled={busy} onClick={() => patch({ credit_per_transaction: parseFloat(rate) }, "บันทึก rate แล้ว")}>บันทึก</button>
        </div>
      </div>

      <div style={{ marginTop: 14 }}>
        <div className="lbl">Ingest key สำหรับแอป forwarder เติมเงิน (ส่งมาที่ <span className="mono">{ingestUrl}</span> ใน header <span className="mono">X-Ingest-Key</span>)</div>
        <div style={{ display: "flex", gap: 8, marginTop: 6, flexWrap: "wrap" }}>
          <input readOnly className="mono" value={s.topup_ingest_key} onFocus={(e) => e.target.select()} style={{ flex: 1, minWidth: 240 }} />
          <button className="btn ghost" disabled={busy}
                  onClick={() => { if (confirm("สร้าง key ใหม่? key เดิมจะใช้ไม่ได้ทันที")) patch({ regenerate_ingest_key: true }, "สร้าง key ใหม่แล้ว"); }}>
            สร้างใหม่
          </button>
        </div>
      </div>
    </div>
  );
}

export default function AdminDashboard() {
  const [stats, setStats] = useState(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    adminApi.stats().then(setStats).catch((e) => setErr(e.message));
  }, []);

  return (
    <div>
      <h1 className="page-title">ภาพรวมระบบ</h1>
      <p className="page-sub">สรุปยอดและกิจกรรมของทุกร้านค้าบนแพลตฟอร์ม</p>
      {err && <div className="error">{err}</div>}

      <PlatformSettings onError={setErr} />
      {!stats ? (
        <div className="muted">กำลังโหลด…</div>
      ) : (
        <>
          <div style={{ display: "flex", gap: 14, flexWrap: "wrap", marginBottom: 14 }}>
            <Stat label="ร้านค้าทั้งหมด" value={stats.merchant_count} />
            <Stat label="ถูกระงับ" value={stats.suspended_count} accent={stats.suspended_count ? "#ef4444" : undefined} />
            <Stat label="รายการชำระแล้ว" value={stats.paid_count} />
            <Stat label="รอชำระ" value={stats.pending_count} />
          </div>
          <div style={{ display: "flex", gap: 14, flexWrap: "wrap" }}>
            <Stat label="ยอดชำระรวม" value={baht(stats.total_paid_amount)} accent="#22c55e" />
            <Stat label="ยอดวันนี้" value={baht(stats.today_amount)} />
            <Stat label="รายการวันนี้" value={stats.today_count} />
            <Stat label="ค่าธรรมเนียมที่เก็บได้ (paid out)" value={baht(stats.total_fee_amount)} accent="#f59e0b" />
          </div>
        </>
      )}
    </div>
  );
}
