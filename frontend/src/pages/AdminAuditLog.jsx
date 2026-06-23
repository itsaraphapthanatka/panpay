import { useEffect, useState } from "react";
import { adminApi } from "../api.js";

const fmt = (d) => (d ? new Date(d).toLocaleString("th-TH") : "—");

export default function AdminAuditLog() {
  const [logs, setLogs] = useState([]);
  const [err, setErr] = useState("");

  useEffect(() => {
    adminApi.auditLogs().then(setLogs).catch((e) => setErr(e.message));
  }, []);

  return (
    <div>
      <h1 className="page-title">บันทึกกิจกรรม (ทั้งระบบ)</h1>
      <p className="page-sub">กิจกรรมด้านความปลอดภัยและการเงินของทุกร้านค้า รวมถึงการกระทำของผู้ดูแล</p>
      {err && <div className="error">{err}</div>}

      <div className="card">
        <table>
          <thead>
            <tr>
              <th>เวลา</th>
              <th>ผู้กระทำ</th>
              <th>การกระทำ</th>
              <th>เป้าหมาย</th>
              <th>IP</th>
            </tr>
          </thead>
          <tbody>
            {logs.map((l) => (
              <tr key={l.id}>
                <td className="muted">{fmt(l.created_at)}</td>
                <td>{l.actor}</td>
                <td className="mono">{l.action}</td>
                <td className="muted">{l.target_type ? `${l.target_type}:${(l.target_id || "").slice(0, 12)}` : "—"}</td>
                <td className="muted">{l.ip || "—"}</td>
              </tr>
            ))}
            {logs.length === 0 && (
              <tr>
                <td colSpan={5} className="muted" style={{ textAlign: "center", padding: 28 }}>ไม่มีบันทึก</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
