import { useEffect, useState } from "react";
import { api } from "../api.js";

const fmt = (d) => (d ? new Date(d).toLocaleString("th-TH") : "—");

const ACTION_LABELS = {
  "auth.login": "เข้าสู่ระบบ",
  "auth.register": "สมัครร้านค้า",
  "settings.update": "แก้ไขการตั้งค่า",
  "api_key.create": "สร้าง API key",
  "api_key.revoke": "เพิกถอน API key",
  "receiving_account.create": "เพิ่มบัญชีรับเงิน",
  "charge.create": "สร้างรายการ",
  "charge.void": "ยกเลิกรายการ",
  "charge.refund": "คืนเงิน",
};

export default function AuditLog() {
  const [logs, setLogs] = useState([]);
  const [err, setErr] = useState("");

  useEffect(() => {
    api.auditLogs().then(setLogs).catch((e) => setErr(e.message));
  }, []);

  return (
    <div>
      <h1 className="page-title">บันทึกกิจกรรม</h1>
      <p className="page-sub">ประวัติการกระทำสำคัญด้านความปลอดภัยและการเงิน (append-only)</p>
      {err && <div className="error">{err}</div>}

      <div className="card">
        <table>
          <thead>
            <tr>
              <th>เวลา</th>
              <th>การกระทำ</th>
              <th>ผู้กระทำ</th>
              <th>เป้าหมาย</th>
              <th>IP</th>
            </tr>
          </thead>
          <tbody>
            {logs.map((l) => (
              <tr key={l.id}>
                <td className="muted">{fmt(l.created_at)}</td>
                <td>{ACTION_LABELS[l.action] || l.action}</td>
                <td>{l.actor}</td>
                <td className="mono">{l.target_id ? l.target_id.slice(0, 18) + "…" : "—"}</td>
                <td className="mono">{l.ip || "—"}</td>
              </tr>
            ))}
            {logs.length === 0 && (
              <tr>
                <td colSpan={5} className="muted" style={{ textAlign: "center", padding: 24 }}>
                  ยังไม่มีบันทึก
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
