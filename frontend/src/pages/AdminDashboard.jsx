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

function AutoCheckToggle({ onError }) {
  const [enabled, setEnabled] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    adminApi.getSettings().then((s) => setEnabled(s.auto_bank_check)).catch((e) => onError(e.message));
  }, []);

  async function toggle() {
    setBusy(true);
    try {
      const s = await adminApi.updateSettings({ auto_bank_check: !enabled });
      setEnabled(s.auto_bank_check);
    } catch (e) {
      onError(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 16, marginBottom: 14, flexWrap: "wrap" }}>
      <div>
        <strong>ตรวจเงินเข้าอัตโนมัติ (Bank Auto-check)</strong>
        <div className="muted" style={{ fontSize: 13, marginTop: 4 }}>
          รับแจ้งเงินเข้าจากแอปธนาคารผ่าน <span className="mono">/bank/incoming</span> แล้วยืนยันการชำระเงินให้อัตโนมัติ
          {enabled === false && " — ปิดอยู่: เงินเข้าจะไม่ถูกตรวจอัตโนมัติ (ใช้แนบสลิปแทน)"}
        </div>
      </div>
      <button
        className={`btn ${enabled ? "danger" : ""}`}
        disabled={busy || enabled === null}
        onClick={toggle}
        style={{ minWidth: 110 }}
      >
        {enabled === null ? "…" : enabled ? "ปิดใช้งาน" : "เปิดใช้งาน"}
      </button>
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

      <AutoCheckToggle onError={setErr} />
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
