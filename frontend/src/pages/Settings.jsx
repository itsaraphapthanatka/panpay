import { useEffect, useState } from "react";
import { useAuth } from "../auth.jsx";
import { api } from "../api.js";

function ReceivingAccounts({ onError }) {
  const [accounts, setAccounts] = useState([]);
  const [form, setForm] = useState({ name: "", promptpay_id: "" });

  async function load() {
    try {
      setAccounts(await api.listAccounts());
    } catch (e) {
      onError(e.message);
    }
  }
  useEffect(() => {
    load();
  }, []);

  async function add(e) {
    e.preventDefault();
    try {
      await api.createAccount(form);
      setForm({ name: "", promptpay_id: "" });
      load();
    } catch (e) {
      onError(e.message);
    }
  }

  return (
    <div className="card">
      <strong>บัญชีรับเงิน (PromptPay หลายบัญชี)</strong>
      <p className="muted" style={{ fontSize: 13 }}>
        เลือกบัญชีปลายทางได้ตอนสร้างรายการ — เช่น แยกตามสาขา/สินค้า
      </p>
      <table style={{ marginTop: 6 }}>
        <tbody>
          {accounts.map((a) => (
            <tr key={a.id}>
              <td>
                {a.name}
                {a.is_default && <span className="badge paid" style={{ marginLeft: 8 }}>ค่าเริ่มต้น</span>}
              </td>
              <td className="mono">{a.promptpay_id}</td>
              <td style={{ textAlign: "right" }}>
                {!a.is_default && (
                  <button className="btn ghost" style={{ padding: "4px 10px", marginRight: 6 }} onClick={() => api.setDefaultAccount(a.id).then(load)}>
                    ตั้งเป็นหลัก
                  </button>
                )}
                <button className="btn danger" style={{ padding: "4px 10px" }} onClick={() => api.deleteAccount(a.id).then(load).catch((e) => onError(e.message))}>
                  ลบ
                </button>
              </td>
            </tr>
          ))}
          {accounts.length === 0 && (
            <tr><td className="muted" style={{ padding: 12 }}>ยังไม่มีบัญชีรับเงินเพิ่มเติม (ใช้ PromptPay ID หลักด้านซ้าย)</td></tr>
          )}
        </tbody>
      </table>
      <form onSubmit={add} style={{ display: "flex", gap: 8, alignItems: "flex-end", marginTop: 12 }}>
        <label className="field" style={{ flex: 1, marginBottom: 0 }}>
          <span className="lbl">ชื่อบัญชี</span>
          <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="สาขาสีลม" required />
        </label>
        <label className="field" style={{ flex: 1, marginBottom: 0 }}>
          <span className="lbl">PromptPay ID</span>
          <input value={form.promptpay_id} onChange={(e) => setForm({ ...form, promptpay_id: e.target.value })} placeholder="0812345678" required />
        </label>
        <button className="btn">เพิ่ม</button>
      </form>
    </div>
  );
}

export default function Settings() {
  const { merchant, refresh } = useAuth();
  const [form, setForm] = useState({ business_name: "", promptpay_id: "", webhook_url: "", bank_account: "" });
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (merchant)
      setForm({
        business_name: merchant.business_name || "",
        promptpay_id: merchant.promptpay_id || "",
        webhook_url: merchant.webhook_url || "",
        bank_account: merchant.bank_account || "",
      });
  }, [merchant]);

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  async function save(e) {
    e.preventDefault();
    setErr("");
    setMsg("");
    setBusy(true);
    try {
      await api.updateSettings(form);
      await refresh();
      setMsg("บันทึกแล้ว");
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <h1 className="page-title">ตั้งค่า</h1>
      <p className="page-sub">ข้อมูลร้านค้า บัญชีรับเงิน และ Webhook</p>
      {err && <div className="error">{err}</div>}
      {msg && <div className="notice">{msg}</div>}

      <div className="grid cols-2">
        <form className="card" onSubmit={save}>
          <strong>ข้อมูลร้านค้า</strong>
          <label className="field" style={{ marginTop: 12 }}>
            <span className="lbl">ชื่อร้านค้า</span>
            <input value={form.business_name} onChange={set("business_name")} />
          </label>
          <label className="field">
            <span className="lbl">PromptPay ID หลัก (เบอร์มือถือ / เลขบัตรประชาชน)</span>
            <input value={form.promptpay_id} onChange={set("promptpay_id")} placeholder="0812345678" />
          </label>
          <label className="field">
            <span className="lbl">Webhook URL (รับแจ้งเตือนเมื่อชำระ/คืนเงิน)</span>
            <input value={form.webhook_url} onChange={set("webhook_url")} placeholder="https://your-shop.com/webhook" />
          </label>
          <label className="field">
            <span className="lbl">เลขบัญชีที่ใช้โอนเติมเงิน (ช่วยจับคู่เงินเข้าอัตโนมัติเมื่อยอดซ้ำ)</span>
            <input value={form.bank_account} onChange={set("bank_account")} placeholder="เลขบัญชีธนาคารของร้าน" />
          </label>
          <button className="btn" disabled={busy}>
            {busy ? "กำลังบันทึก…" : "บันทึกการตั้งค่า"}
          </button>
        </form>

        <div className="card">
          <strong>Webhook Secret</strong>
          <p className="muted" style={{ fontSize: 13 }}>
            ใช้ตรวจสอบลายเซ็น <code>X-Panpay-Signature</code> (HMAC-SHA256). อีเวนต์: <code>charge.paid</code>,{" "}
            <code>charge.refunded</code>, <code>charge.canceled</code>, <code>subscription.activated</code>,{" "}
            <code>subscription.renewed</code>, <code>subscription.canceled</code>, <code>subscription.expired</code>
          </p>
          <input readOnly className="mono" value={merchant?.webhook_secret || ""} onFocus={(e) => e.target.select()} />
          <pre className="mono" style={{ overflowX: "auto", background: "var(--surface-2)", padding: 12, borderRadius: 10, marginTop: 12, fontSize: 12 }}>
{`import hmac, hashlib
sig = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
assert sig == request.headers["X-Panpay-Signature"]`}
          </pre>
        </div>
      </div>

      <div style={{ marginTop: 16 }}>
        <ReceivingAccounts onError={setErr} />
      </div>
    </div>
  );
}
