import { useEffect, useState } from "react";
import { api, API_URL } from "../api.js";
import { useDialog } from "../components/Dialog.jsx";

const fmt = (d) => (d ? new Date(d).toLocaleString("th-TH") : "—");

export default function ApiKeys() {
  const [keys, setKeys] = useState([]);
  const [name, setName] = useState("");
  const [newSecret, setNewSecret] = useState(null);
  const [err, setErr] = useState("");
  const ui = useDialog();

  async function load() {
    try {
      setKeys(await api.listKeys());
    } catch (e) {
      setErr(e.message);
    }
  }
  useEffect(() => {
    load();
  }, []);

  async function create(e) {
    e.preventDefault();
    setErr("");
    try {
      const k = await api.createKey({ name: name || "Secret key" });
      setNewSecret(k.secret);
      setName("");
      load();
    } catch (e) {
      setErr(e.message);
    }
  }

  async function revoke(id) {
    if (!(await ui.confirm({ title: "เพิกถอน API key", message: "เพิกถอน API key นี้? ระบบที่ใช้คีย์นี้จะเรียก API ไม่ได้ทันที", confirmLabel: "เพิกถอน", danger: true }))) return;
    await api.revokeKey(id);
    load();
  }

  return (
    <div>
      <h1 className="page-title">API Keys</h1>
      <p className="page-sub">ใช้คีย์นี้เรียก API สร้างรายการชำระเงินจากระบบของคุณ</p>
      {err && <div className="error">{err}</div>}

      {newSecret && (
        <div className="card" style={{ marginBottom: 16, borderColor: "#c7d2fe" }}>
          <div className="notice" style={{ marginBottom: 8 }}>
            คัดลอกคีย์นี้ทันที — จะไม่แสดงอีก
          </div>
          <input readOnly className="mono" value={newSecret} onFocus={(e) => e.target.select()} />
          <button className="btn ghost" style={{ marginTop: 10 }} onClick={() => setNewSecret(null)}>
            เรียบร้อย
          </button>
        </div>
      )}

      <div className="card" style={{ marginBottom: 16 }}>
        <form onSubmit={create} style={{ display: "flex", gap: 10, alignItems: "flex-end" }}>
          <label className="field" style={{ flex: 1, marginBottom: 0 }}>
            <span className="lbl">ชื่อคีย์</span>
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="เช่น production" />
          </label>
          <button className="btn">สร้าง API Key</button>
        </form>
      </div>

      <div className="card">
        <table>
          <thead>
            <tr>
              <th>ชื่อ</th>
              <th>คีย์</th>
              <th>สถานะ</th>
              <th>ใช้ล่าสุด</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {keys.map((k) => (
              <tr key={k.id}>
                <td>{k.name}</td>
                <td className="mono">{k.prefix}…{k.last_four}</td>
                <td>{k.revoked ? <span className="badge expired">เพิกถอนแล้ว</span> : <span className="badge paid">ใช้งานได้</span>}</td>
                <td className="muted">{fmt(k.last_used_at)}</td>
                <td>
                  {!k.revoked && (
                    <button className="btn danger" onClick={() => revoke(k.id)}>
                      เพิกถอน
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {keys.length === 0 && (
              <tr>
                <td colSpan={5} className="muted" style={{ textAlign: "center", padding: 24 }}>
                  ยังไม่มี API key
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="card" style={{ marginTop: 16 }}>
        <strong>ตัวอย่างการเรียก API</strong>
        <pre className="mono" style={{ overflowX: "auto", background: "var(--surface-2)", padding: 14, borderRadius: 10, marginTop: 10 }}>
{`curl -X POST ${API_URL}/v1/charges \\
  -H "Authorization: Bearer sk_live_xxx" \\
  -H "Content-Type: application/json" \\
  -d '{"amount": 100.00, "reference": "order-123", "description": "ค่าสินค้า"}'`}
        </pre>
      </div>
    </div>
  );
}
