import { useEffect, useRef, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { api, receiptUrl } from "../api.js";

const baht = (n) => "฿" + Number(n).toLocaleString("th-TH", { minimumFractionDigits: 2 });

export default function Checkout() {
  const { chargeId } = useParams();
  const [params] = useSearchParams();
  const embed = params.get("embed") === "1";
  const [charge, setCharge] = useState(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const fileRef = useRef(null);

  // In embed mode, notify the parent page (panpay.js) when payment completes.
  useEffect(() => {
    if (embed && charge?.status === "paid") {
      window.parent?.postMessage(
        { type: "panpay:paid", chargeId, status: "paid", amount: charge.amount },
        "*"
      );
    }
  }, [embed, charge?.status, chargeId]);

  const closeEmbed = () =>
    window.parent?.postMessage({ type: "panpay:close", chargeId }, "*");

  async function load() {
    try {
      setCharge(await api.checkout(chargeId));
    } catch (e) {
      setErr(e.message);
    }
  }
  useEffect(() => {
    load();
  }, [chargeId]);

  // While pending, poll so an externally-verified payment updates the page.
  useEffect(() => {
    if (charge?.status !== "pending") return;
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, [charge?.status]);

  async function submitSlip(e) {
    e.preventDefault();
    setErr("");
    setBusy(true);
    try {
      const fd = new FormData();
      const file = fileRef.current?.files?.[0];
      if (file) {
        fd.append("file", file);
      } else {
        // No slip image attached — send a client reference (works in dev provider).
        fd.append("trans_ref", "WEB" + Date.now());
      }
      const updated = await api.submitSlip(chargeId, fd);
      setCharge(updated);
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  if (!charge) {
    return (
      <div className={`pay-wrap${embed ? " embed" : ""}`}>
        <div className="pay-card">
          <div className="pay-body">{err ? <div className="error">{err}</div> : "กำลังโหลด…"}</div>
        </div>
      </div>
    );
  }

  const paid = charge.status === "paid";
  const expired = charge.status === "expired";

  return (
    <div className={`pay-wrap${embed ? " embed" : ""}`}>
      <div className="pay-card">
        <div className="pay-head">
          {embed && (
            <button onClick={closeEmbed} aria-label="close" className="embed-close">
              ✕
            </button>
          )}
          <div style={{ opacity: 0.85, fontSize: 13 }}>{charge.business_name}</div>
          <div style={{ fontSize: 13, opacity: 0.8 }}>{charge.description || "ชำระเงิน"}</div>
          <div className="amount-big">{baht(charge.amount)}</div>
        </div>
        <div className="pay-body">
          {err && <div className="error">{err}</div>}

          {paid ? (
            <>
              <div className="paid-check">✓</div>
              <h2 style={{ margin: 0 }}>ชำระเงินสำเร็จ</h2>
              <p className="muted">ขอบคุณครับ ระบบได้รับการชำระเงินเรียบร้อยแล้ว</p>
              {charge.payment && (
                <div style={{ background: "var(--surface-2)", borderRadius: 12, padding: 16, textAlign: "left", fontSize: 13, marginTop: 8 }}>
                  {charge.payment.sender_bank && (
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                      <span className="muted">ธนาคารต้นทาง</span><span>{charge.payment.sender_bank}</span>
                    </div>
                  )}
                  {charge.payment.transferred_at && (
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                      <span className="muted">เวลาโอน</span><span>{new Date(charge.payment.transferred_at).toLocaleString("th-TH")}</span>
                    </div>
                  )}
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span className="muted">เลขอ้างอิง</span>
                    <span className="mono" style={{ wordBreak: "break-all", textAlign: "right", maxWidth: "60%" }}>{charge.payment.trans_ref}</span>
                  </div>
                </div>
              )}
              <a className="btn block" style={{ marginTop: 16 }} href={receiptUrl(chargeId)} target="_blank" rel="noreferrer">
                ดาวน์โหลดใบเสร็จ (PDF)
              </a>
            </>
          ) : expired ? (
            <>
              <h2>รายการหมดอายุ</h2>
              <p className="muted">QR นี้หมดอายุแล้ว กรุณาติดต่อร้านค้า</p>
            </>
          ) : (
            <>
              <div className="qr-box">
                <img src={charge.qr_image} alt="PromptPay QR" />
              </div>
              <p className="muted" style={{ marginTop: 14 }}>
                1. สแกนด้วยแอปธนาคารเพื่อจ่ายผ่าน PromptPay
                <br />
                2. <strong>แนบรูปสลิป</strong> ด้านล่างเพื่อยืนยันการชำระเงิน
              </p>
              <form onSubmit={submitSlip} style={{ marginTop: 12 }}>
                <input ref={fileRef} type="file" accept="image/*" style={{ marginBottom: 12 }} />
                <button className="btn block" disabled={busy}>
                  {busy ? "กำลังตรวจสอบสลิป…" : "แนบสลิปเพื่อยืนยันการชำระเงิน"}
                </button>
              </form>
              <p className="muted" style={{ fontSize: 12, marginTop: 14, display: "flex", alignItems: "center", justifyContent: "center", gap: 8 }}>
                <span className="pay-spinner" aria-hidden="true" />
                หรือรอระบบตรวจสอบอัตโนมัติ (หากเปิดใช้งานไว้)
              </p>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
