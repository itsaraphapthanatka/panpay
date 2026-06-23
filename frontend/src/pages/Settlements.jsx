import { useEffect, useState } from "react";
import { api, downloadFile } from "../api.js";

const baht = (n) => "฿" + Number(n).toLocaleString("th-TH", { minimumFractionDigits: 2 });
const fmt = (d) => (d ? new Date(d).toLocaleString("th-TH") : "—");

export default function Settlements() {
  const [rows, setRows] = useState([]);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  async function load() {
    try {
      setRows(await api.listSettlements());
    } catch (e) {
      setErr(e.message);
    }
  }
  useEffect(() => {
    load();
  }, []);

  async function generate() {
    setErr("");
    setBusy(true);
    try {
      await api.generateSettlement({});
      load();
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function doPayout(id) {
    const reference = prompt("อ้างอิงการจ่ายเงิน (เลขที่โอน ฯลฯ):") ?? null;
    try {
      await api.payout(id, reference);
      load();
    } catch (e) {
      setErr(e.message);
    }
  }

  return (
    <div>
      <h1 className="page-title">Settlement / การจ่ายเงิน</h1>
      <p className="page-sub">จัดรอบยอดที่รับชำระแล้ว หักค่าธรรมเนียม และทำรายการจ่ายออก</p>
      {err && <div className="error">{err}</div>}

      <div className="notice" style={{ marginBottom: 14 }}>
        เงินเข้าบัญชีร้านค้าโดยตรงผ่าน PromptPay — รอบ settlement นี้ใช้สำหรับ <b>กระทบยอด/หักค่าธรรมเนียม/ออกรายงาน</b> ไม่ใช่การถือเงินแทน
      </div>

      <div style={{ marginBottom: 14 }}>
        <button className="btn" onClick={generate} disabled={busy}>
          {busy ? "กำลังสร้าง…" : "+ สร้างรอบ settlement (จากยอดที่ยังไม่กระทบ)"}
        </button>
      </div>

      <div className="card">
        <table>
          <thead>
            <tr>
              <th>รหัส</th>
              <th>ช่วงเวลา</th>
              <th>ยอดรวม</th>
              <th>ค่าธรรมเนียม</th>
              <th>ยอดสุทธิ</th>
              <th>จำนวน</th>
              <th>สถานะ</th>
              <th>จัดการ</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((s) => (
              <tr key={s.id}>
                <td className="mono">{s.id.slice(0, 12)}…</td>
                <td className="muted" style={{ fontSize: 12 }}>
                  {fmt(s.period_start)}
                  <br />– {fmt(s.period_end)}
                </td>
                <td>{baht(s.gross_amount)}</td>
                <td className="muted">−{baht(s.fee_amount)}</td>
                <td><b>{baht(s.net_amount)}</b></td>
                <td>{s.charge_count}</td>
                <td>
                  <span className={`badge ${s.status === "paid_out" ? "paid" : "pending"}`}>
                    {s.status === "paid_out" ? "จ่ายแล้ว" : "รอจ่าย"}
                  </span>
                </td>
                <td>
                  <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                    <button
                      className="btn ghost"
                      style={{ padding: "4px 10px" }}
                      onClick={() => downloadFile(`/dashboard/settlements/${s.id}/export.csv`, `settlement-${s.id}.csv`).catch((e) => setErr(e.message))}
                    >
                      CSV
                    </button>
                    {s.status !== "paid_out" && (
                      <button className="btn" style={{ padding: "4px 10px" }} onClick={() => doPayout(s.id)}>
                        ทำจ่าย
                      </button>
                    )}
                    {s.reference && <span className="mono muted" style={{ fontSize: 12 }}>{s.reference}</span>}
                  </div>
                </td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={8} className="muted" style={{ textAlign: "center", padding: 28 }}>
                  ยังไม่มีรอบ settlement
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
