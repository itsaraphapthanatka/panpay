import { useEffect, useRef, useState } from "react";
import { api } from "../api.js";
import { useDialog } from "../components/Dialog.jsx";

const baht = (n) => "฿" + Number(n).toLocaleString("th-TH", { minimumFractionDigits: 2 });
const fmt = (d) => (d ? new Date(d).toLocaleString("th-TH") : "—");

const TOPUP_LABELS = { pending: "รอชำระ", completed: "สำเร็จ", expired: "หมดอายุ", canceled: "ยกเลิก" };
const TOPUP_BADGE = { pending: "pending", completed: "paid", expired: "expired", canceled: "canceled" };

function ActiveTopup({ topup, onDone, onError }) {
  const [t, setT] = useState(topup);
  const [busy, setBusy] = useState(false);
  const fileRef = useRef(null);
  const ui = useDialog();

  // Poll until the auto bank-capture (or slip) settles it.
  useEffect(() => {
    if (t.status !== "pending") {
      if (t.status === "completed") onDone();
      return;
    }
    const iv = setInterval(async () => {
      try {
        const fresh = await api.getTopup(t.id);
        setT(fresh);
        if (fresh.status === "completed") {
          clearInterval(iv);
          onDone();
        }
      } catch (e) {
        /* keep polling */
      }
    }, 5000);
    return () => clearInterval(iv);
  }, [t.status, t.id]);

  async function uploadSlip(e) {
    e.preventDefault();
    setBusy(true);
    try {
      const fd = new FormData();
      const f = fileRef.current?.files?.[0];
      if (!f) throw new Error("เลือกไฟล์สลิปก่อน");
      fd.append("file", f);
      const fresh = await api.topupSlip(t.id, fd);
      setT(fresh);
      if (fresh.status === "completed") onDone();
    } catch (e) {
      onError(e.message);
    } finally {
      setBusy(false);
    }
  }

  if (t.status === "completed") {
    return (
      <div className="card" style={{ borderColor: "#bbf7d0" }}>
        <div className="notice">✓ เติมเงินสำเร็จ {baht(t.pay_amount)} — เครดิตเข้าบัญชีแล้ว</div>
      </div>
    );
  }

  return (
    <div className="card" style={{ borderColor: "#c7d2fe" }}>
      <strong>สแกนเพื่อเติมเงิน</strong>
      <p className="muted" style={{ fontSize: 13, marginTop: 4 }}>
        โอนยอด <strong style={{ color: "var(--text)" }}>{baht(t.pay_amount)}</strong> ให้ตรงเป๊ะ (เศษสตางค์ใช้จับคู่อัตโนมัติ)
      </p>
      <div className="qr-box" style={{ maxWidth: 240, margin: "10px auto" }}>
        <img src={t.qr_image} alt="PromptPay QR" style={{ width: "100%" }} />
      </div>
      <div className="notice" style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 10 }}>
        <span className="pay-spinner" aria-hidden="true" />
        กำลังรอตรวจสอบการโอนอัตโนมัติ…
      </div>
      <form onSubmit={uploadSlip} style={{ marginTop: 12 }}>
        <p className="muted" style={{ fontSize: 12, marginBottom: 6 }}>หรือแนบสลิปเพื่อยืนยันทันที</p>
        <input ref={fileRef} type="file" accept="image/*" style={{ marginBottom: 10 }} />
        <button className="btn block" disabled={busy}>{busy ? "กำลังตรวจสลิป…" : "ยืนยันด้วยสลิป"}</button>
      </form>
      <button
        className="btn danger block"
        style={{ marginTop: 10 }}
        disabled={busy}
        onClick={async () => {
          if (!(await ui.confirm({ title: "ยกเลิกการเติมเงิน", message: "ยกเลิกรายการเติมเงินนี้?", confirmLabel: "ยกเลิกรายการ", danger: true }))) return;
          setBusy(true);
          try {
            await api.cancelTopup(t.id);
            onDone();
          } catch (e) {
            onError(e.message);
          } finally {
            setBusy(false);
          }
        }}
      >
        ยกเลิกรายการนี้
      </button>
    </div>
  );
}

export default function Topup() {
  const [data, setData] = useState(null);
  const [topups, setTopups] = useState([]);
  const [amount, setAmount] = useState("");
  const [active, setActive] = useState(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const ui = useDialog();

  async function load() {
    try {
      const [b, list] = await Promise.all([api.balance(), api.listTopups()]);
      setData(b);
      setTopups(list);
    } catch (e) {
      setErr(e.message);
    }
  }
  useEffect(() => { load(); }, []);

  async function create(e) {
    e.preventDefault();
    setErr("");
    setBusy(true);
    try {
      const t = await api.createTopup(parseFloat(amount));
      setActive(t);
      setAmount("");
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function cancelRow(id) {
    if (!(await ui.confirm({ title: "ยกเลิกการเติมเงิน", message: "ยกเลิกรายการเติมเงินนี้?", confirmLabel: "ยกเลิกรายการ", danger: true }))) return;
    try {
      await api.cancelTopup(id);
      if (active?.id === id) setActive(null);
      load();
    } catch (e) {
      setErr(e.message);
    }
  }

  async function payRow(id) {
    setErr("");
    try {
      // listTopups omits the QR; fetch the full record to re-open the QR to pay.
      setActive(await api.getTopup(id));
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (e) {
      setErr(e.message);
    }
  }

  return (
    <div>
      <h1 className="page-title">เติมเงิน / เครดิต</h1>
      <p className="page-sub">เติมเครดิตเพื่อใช้รับชำระเงิน — ระบบหักเครดิตต่อรายการที่รับเงินสำเร็จ</p>
      {err && <div className="error">{err}</div>}

      {data && (
        <div className="grid cols-2" style={{ marginBottom: 16 }}>
          <div className="card">
            <div className="stat-label">เครดิตคงเหลือ</div>
            <div className="stat-value" style={{ color: data.balance > 0 ? "#22c55e" : "#ef4444" }}>
              {baht(data.balance)}
            </div>
            <div className="muted" style={{ fontSize: 12 }}>
              หักรายการละ {baht(data.credit_per_transaction)} · รับได้อีก ~{Math.floor(data.balance / (data.credit_per_transaction || 0.5))} รายการ
            </div>
          </div>
          <form className="card" onSubmit={create}>
            <strong>เติมเครดิต</strong>
            <div style={{ display: "flex", gap: 8, alignItems: "flex-end", marginTop: 10, flexWrap: "wrap" }}>
              <label className="field" style={{ flex: 1, marginBottom: 0, minWidth: 120 }}>
                <span className="lbl">จำนวนเงิน (฿)</span>
                <input type="number" step="1" min="1" value={amount} onChange={(e) => setAmount(e.target.value)} placeholder="100" required />
              </label>
              <div style={{ display: "flex", gap: 6 }}>
                {[100, 300, 500].map((v) => (
                  <button type="button" key={v} className="btn ghost" style={{ padding: "8px 10px" }} onClick={() => setAmount(String(v))}>{v}</button>
                ))}
              </div>
              <button className="btn" disabled={busy}>{busy ? "…" : "สร้าง QR เติมเงิน"}</button>
            </div>
          </form>
        </div>
      )}

      {active && (
        <div style={{ marginBottom: 16 }}>
          <ActiveTopup topup={active} onError={setErr} onDone={() => { setActive(null); load(); }} />
        </div>
      )}

      <div className="card" style={{ marginBottom: 16 }}>
        <strong>ประวัติการเติมเงิน</strong>
        <table style={{ marginTop: 8 }}>
          <thead><tr><th>วันที่</th><th>ยอดที่โอน</th><th>วิธี</th><th>สถานะ</th><th>จัดการ</th></tr></thead>
          <tbody>
            {topups.map((t) => (
              <tr key={t.id}>
                <td className="muted">{fmt(t.created_at)}</td>
                <td>{baht(t.pay_amount)}</td>
                <td className="muted">{t.method === "bank_auto" ? "อัตโนมัติ" : t.method === "slip" ? "สลิป" : "—"}</td>
                <td><span className={`badge ${TOPUP_BADGE[t.status]}`}>{TOPUP_LABELS[t.status] || t.status}</span></td>
                <td>
                  {t.status === "pending" && (
                    <div style={{ display: "flex", gap: 6 }}>
                      <button className="btn" style={{ padding: "4px 10px" }} onClick={() => payRow(t.id)}>ดู QR / จ่าย</button>
                      <button className="btn danger" style={{ padding: "4px 10px" }} onClick={() => cancelRow(t.id)}>ยกเลิก</button>
                    </div>
                  )}
                </td>
              </tr>
            ))}
            {topups.length === 0 && <tr><td colSpan={5} className="muted" style={{ textAlign: "center", padding: 20 }}>ยังไม่มีรายการเติมเงิน</td></tr>}
          </tbody>
        </table>
      </div>

      {data?.entries?.length > 0 && (
        <div className="card">
          <strong>เดินบัญชีเครดิต (ล่าสุด)</strong>
          <table style={{ marginTop: 8 }}>
            <thead><tr><th>วันที่</th><th>รายการ</th><th>จำนวน</th><th>คงเหลือ</th></tr></thead>
            <tbody>
              {data.entries.map((e) => (
                <tr key={e.id}>
                  <td className="muted" style={{ fontSize: 12 }}>{fmt(e.created_at)}</td>
                  <td>{e.description || e.type}</td>
                  <td style={{ color: e.amount >= 0 ? "#22c55e" : "#ef4444" }}>
                    {e.amount >= 0 ? "+" : ""}{baht(e.amount)}
                  </td>
                  <td className="muted">{baht(e.balance_after)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
