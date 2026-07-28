import { useEffect, useState } from "react";
import { adminApi } from "../api.js";
import { useDialog } from "../components/Dialog.jsx";

function Switch({ checked, disabled, onChange }) {
  return (
    <label className="switch">
      <input type="checkbox" checked={!!checked} disabled={disabled} onChange={(e) => onChange(e.target.checked)} />
      <span className="track" />
    </label>
  );
}

function LineBotSection() {
  const [bot, setBot] = useState(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const ui = useDialog();

  async function load() {
    try { setBot(await adminApi.lineBot()); setErr(""); } catch (e) { setErr(e.message); }
  }
  useEffect(() => {
    load();
    const t = setInterval(load, 4000);
    return () => clearInterval(t);
  }, []);

  async function reconnect() {
    const ok = await ui.confirm({
      title: "เชื่อม LINE ใหม่",
      message: "ตัดการเชื่อมต่อบัญชีเดิมแล้วขึ้น QR ใหม่? บอทจะหยุดอ่านเงินเข้าชั่วครู่จนกว่าจะสแกนบัญชีใหม่",
      confirmLabel: "เชื่อมใหม่", danger: true,
    });
    if (!ok) return;
    setBusy(true);
    try { await adminApi.lineBotReconnect(); await load(); }
    catch (e) { setErr(e.message); } finally { setBusy(false); }
  }

  const status = bot?.status;
  return (
    <div className="card" style={{ marginTop: 16 }}>
      <div className="set-section" style={{ borderBottom: "none", paddingBottom: 0 }}>
        <h3 className="set-head">LINE Bot (อ่านเงินเข้า + เช็คยอด)</h3>
        <p className="set-desc">
          บอท LINE อ่านแจ้งเตือนเงินเข้าเพื่อยืนยันการชำระอัตโนมัติ และตอบข้อความ “ยอดเงิน” — เชื่อมบัญชีโดยสแกน QR
        </p>
        {err && <div className="error">{err}</div>}
        {!bot ? (
          <div className="muted">กำลังโหลด…</div>
        ) : status === "connected" ? (
          <div>
            <div className="notice">✅ เชื่อมแล้ว — บัญชี: <strong>{bot.display_name || "(ไม่ทราบชื่อ)"}</strong></div>
            <button className="btn ghost" disabled={busy} onClick={reconnect} style={{ marginTop: 12 }}>
              {busy ? "กำลังส่งคำขอ…" : "เชื่อมใหม่ / เปลี่ยนบัญชี"}
            </button>
          </div>
        ) : status === "awaiting_qr" && bot.qr_image ? (
          <div style={{ textAlign: "center" }}>
            <p className="muted" style={{ marginBottom: 10 }}>
              เปิดแอป LINE (บัญชีที่รับแจ้งเตือนเงินเข้า) → เมนู … → สแกน QR → ส่องที่โค้ดด้านล่าง
            </p>
            <img src={bot.qr_image} alt="LINE login QR"
                 style={{ width: 260, height: 260, borderRadius: 12, border: "1px solid var(--border, #e2e8f0)" }} />
            <p className="muted" style={{ fontSize: 12, marginTop: 8 }}>
              QR รีเฟรชอัตโนมัติเมื่อหมดอายุ • {bot.reconnect_pending ? "กำลังรอเชื่อมใหม่…" : "รอสแกน…"}
            </p>
          </div>
        ) : (
          <div className="muted" style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span className="pay-spinner" aria-hidden="true" />
            {bot.reconnect_pending ? "กำลังตัดการเชื่อมต่อเพื่อขึ้น QR ใหม่…"
              : status === "starting" ? "บอทกำลังเริ่มทำงาน…"
              : "ยังไม่เชื่อมบัญชี — กำลังรอ QR…"}
          </div>
        )}
      </div>
    </div>
  );
}

export default function AdminSettings() {
  const [s, setS] = useState(null);
  const [pp, setPp] = useState("");
  const [rate, setRate] = useState("");
  const [rname, setRname] = useState("");
  const [racct, setRacct] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const ui = useDialog();

  function sync(v) {
    setS(v);
    setPp(v.platform_promptpay || "");
    setRate(String(v.credit_per_transaction));
    setRname(v.platform_receiver_name || "");
    setRacct(v.platform_receiver_account || "");
  }

  async function refresh() {
    try { sync(await adminApi.getSettings()); } catch (e) { setErr(e.message); }
  }
  useEffect(() => { refresh(); }, []);

  async function patch(body, okMsg) {
    setBusy(true);
    setMsg("");
    setErr("");
    try {
      sync(await adminApi.updateSettings(body));
      if (okMsg) setMsg(okMsg);
    } catch (e) { setErr(e.message); } finally { setBusy(false); }
  }

  // Save all the text fields at once — one button instead of three.
  function saveFields() {
    const r = parseFloat(rate);
    if (Number.isNaN(r) || r < 0) { setErr("ค่าบริการต่อรายการต้องเป็นตัวเลขไม่ติดลบ"); return; }
    patch({
      platform_promptpay: pp.trim(),
      platform_receiver_name: rname.trim(),
      platform_receiver_account: racct.trim(),
      credit_per_transaction: r,
    }, "บันทึกการตั้งค่าแล้ว");
  }

  const ingestUrl = `${window.location.origin}/api/topup/incoming`;
  const noReceiver = s && !s.platform_receiver_name && !s.platform_receiver_account;

  return (
    <div>
      <h1 className="page-title">ตั้งค่าแพลตฟอร์ม</h1>
      <p className="page-sub">บัญชีรับเงิน ค่าบริการ การจับยอดเงินเข้า และแอปแจ้งเตือนธนาคาร</p>
      {err && <div className="error">{err}</div>}
      {msg && <div className="notice">{msg}</div>}

      {!s ? (
        <div className="muted">กำลังโหลด…</div>
      ) : (
        <div className="card">
          {/* ── บัญชีรับเงินเติมเครดิต ── */}
          <div className="set-section">
            <h3 className="set-head">บัญชีรับเงิน (เติมเครดิตร้านค้า)</h3>
            <p className="set-desc">
              บัญชี PromptPay ที่ร้านค้าโอนเข้ามาเพื่อเติมเครดิต และชื่อ/เลขบัญชีผู้รับไว้ตรวจสลิป (กันร้านอัปสลิปที่โอนเข้าบัญชีอื่น)
            </p>
            {noReceiver && (
              <div className="error" style={{ marginBottom: 14 }}>
                ⚠️ ยังไม่ได้ตั้ง “ชื่อบัญชีผู้รับ” — การเติมเงินด้วยสลิปจะตรวจแค่ยอด ร้านอาจอัปสลิปที่โอนเข้าบัญชีอื่นเพื่อรับเครดิตฟรีได้
              </div>
            )}
            <div className="grid cols-2" style={{ gap: 12 }}>
              <label className="field" style={{ marginBottom: 0 }}>
                <span className="lbl">PromptPay แพลตฟอร์ม</span>
                <input value={pp} onChange={(e) => setPp(e.target.value)} placeholder="0812345678 / เลขนิติบุคคล" />
              </label>
              <label className="field" style={{ marginBottom: 0 }}>
                <span className="lbl">ค่าบริการต่อรายการ (บาท / transaction)</span>
                <input type="number" step="0.01" min="0" value={rate} onChange={(e) => setRate(e.target.value)} />
              </label>
              <label className="field" style={{ marginBottom: 0 }}>
                <span className="lbl">ชื่อบัญชีผู้รับ (ไม่ใส่คำนำหน้า)</span>
                <input value={rname} onChange={(e) => setRname(e.target.value)} placeholder="ชื่อบัญชีตามสลิป" />
              </label>
              <label className="field" style={{ marginBottom: 0 }}>
                <span className="lbl">เลขบัญชีผู้รับ (ไม่บังคับ)</span>
                <input value={racct} onChange={(e) => setRacct(e.target.value)} placeholder="xxxxxx1234" />
              </label>
            </div>
            <button className="btn" disabled={busy} onClick={saveFields} style={{ marginTop: 14 }}>
              {busy ? "กำลังบันทึก…" : "บันทึกการตั้งค่า"}
            </button>
          </div>

          {/* ── การจับยอดเงินเข้า (toggles) ── */}
          <div className="set-section">
            <h3 className="set-head">การจับยอดเงินเข้า</h3>
            <p className="set-desc">เปลี่ยนแล้วมีผลทันที</p>
            <div className="set-toggle">
              <div>
                <div className="tt">ตรวจเงินเข้าอัตโนมัติ (Bank Auto-check)</div>
                <div className="td">รับแจ้งเตือนจากแอปธนาคารแล้วตัดยอด/เติมเครดิตให้เองโดยไม่ต้องแนบสลิป</div>
              </div>
              <Switch checked={s.auto_bank_check} disabled={busy}
                      onChange={(v) => patch({ auto_bank_check: v })} />
            </div>
            <div className="set-toggle">
              <div>
                <div className="tt">เติมเงินใช้เศษสตางค์</div>
                <div className="td">เติมยอดมีเศษ (เช่น 100.37) เพื่อจับคู่ auto ได้แม่นยำ — ปิด = ยอดเติมเป็นจำนวนกลม</div>
              </div>
              <Switch checked={s.topup_unique_satang} disabled={busy}
                      onChange={(v) => patch({ topup_unique_satang: v })} />
            </div>
          </div>

          {/* ── แอป Forwarder / Ingest key ── */}
          <div className="set-section">
            <h3 className="set-head">แอปแจ้งเตือนธนาคาร (Forwarder)</h3>
            <p className="set-desc">
              แอปส่งข้อมูลเงินเข้ามาที่ <span className="mono">{ingestUrl}</span> พร้อม header{" "}
              <span className="mono">X-Ingest-Key</span> เป็นคีย์ด้านล่าง
            </p>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <input readOnly className="mono" value={s.topup_ingest_key} onFocus={(e) => e.target.select()} style={{ flex: 1, minWidth: 240 }} />
              <button className="btn ghost" disabled={busy}
                      onClick={async () => { if (await ui.confirm({ title: "สร้าง ingest key ใหม่", message: "สร้าง key ใหม่? key เดิมจะใช้ไม่ได้ทันที", confirmLabel: "สร้างใหม่", danger: true })) patch({ regenerate_ingest_key: true }, "สร้าง key ใหม่แล้ว"); }}>
                สร้างใหม่
              </button>
            </div>
          </div>
        </div>
      )}

      <LineBotSection />
    </div>
  );
}
