import { useEffect, useState } from "react";
import { api, API_URL, downloadFile, receiptUrl } from "../api.js";
import StatusBadge from "../components/StatusBadge.jsx";

const baht = (n) => "฿" + Number(n).toLocaleString("th-TH", { minimumFractionDigits: 2 });
const fmt = (d) => (d ? new Date(d).toLocaleString("th-TH") : "—");

function PaymentDetail({ charge }) {
  const p = charge.payment;
  return (
    <div style={{ background: "var(--surface-2)", borderRadius: 10, padding: 14, fontSize: 13 }}>
      {charge.status === "refunded" && (
        <div className="notice" style={{ marginBottom: 10 }}>
          คืนเงินแล้วเมื่อ {fmt(charge.refunded_at)}
          {charge.refund_reason ? ` · เหตุผล: ${charge.refund_reason}` : ""}
          <br />
          <span className="muted">หมายเหตุ: PanPay บันทึกการคืนเงิน ร้านค้าต้องโอนเงินคืนลูกค้าเอง (เงินเข้าบัญชีร้านโดยตรง)</span>
        </div>
      )}
      {p ? (
        <div className="grid cols-2" style={{ gap: 8 }}>
          <div><span className="muted">เลขอ้างอิงธุรกรรม</span><br /><span className="mono">{p.trans_ref}</span></div>
          <div><span className="muted">เวลาโอน</span><br />{fmt(p.transferred_at)}</div>
          <div><span className="muted">ผู้โอน</span><br />{p.sender_name || "—"}</div>
          <div><span className="muted">ธนาคารต้นทาง</span><br />{p.sender_bank || "—"}</div>
          <div><span className="muted">ผู้รับ</span><br />{p.receiver_name || "—"}</div>
          <div><span className="muted">ผู้ตรวจสอบ</span><br />{p.provider}</div>
        </div>
      ) : (
        <span className="muted">ไม่มีข้อมูลสลิป</span>
      )}
    </div>
  );
}

export default function Transactions() {
  const [charges, setCharges] = useState([]);
  const [filter, setFilter] = useState("");
  const [openId, setOpenId] = useState(null);
  const [err, setErr] = useState("");

  async function load() {
    try {
      setCharges(await api.charges(filter || undefined));
    } catch (e) {
      setErr(e.message);
    }
  }
  useEffect(() => {
    load();
  }, [filter]);

  async function doVoid(id) {
    if (!confirm("ยกเลิกรายการนี้?")) return;
    try {
      await api.voidCharge(id);
      load();
    } catch (e) {
      setErr(e.message);
    }
  }
  async function doRefund(id) {
    const reason = prompt("เหตุผลการคืนเงิน (ไม่บังคับ):") ?? null;
    try {
      await api.refundCharge(id, reason);
      load();
    } catch (e) {
      setErr(e.message);
    }
  }

  return (
    <div>
      <h1 className="page-title">รายการชำระเงิน</h1>
      <p className="page-sub">คลิกแถวที่ชำระแล้วเพื่อดูข้อมูลสลิป · ยกเลิก/คืนเงินได้จากปุ่มท้ายแถว</p>
      {err && <div className="error">{err}</div>}

      <div style={{ display: "flex", gap: 8, marginBottom: 14, flexWrap: "wrap", alignItems: "center" }}>
        {["", "paid", "pending", "refunded", "canceled", "expired"].map((s) => (
          <button key={s} className={`btn ${filter === s ? "" : "ghost"}`} onClick={() => setFilter(s)}>
            {{ "": "ทั้งหมด", paid: "ชำระแล้ว", pending: "รอชำระ", refunded: "คืนเงิน", canceled: "ยกเลิก", expired: "หมดอายุ" }[s]}
          </button>
        ))}
        <div style={{ flex: 1 }} />
        <button
          className="btn ghost"
          onClick={() =>
            downloadFile(`/dashboard/charges/export.csv${filter ? `?status=${filter}` : ""}`, "panpay-transactions.csv").catch((e) => setErr(e.message))
          }
        >
          ⬇ Export CSV
        </button>
      </div>

      <div className="card">
        <table>
          <thead>
            <tr>
              <th>รหัสรายการ</th>
              <th>อ้างอิง</th>
              <th>รายละเอียด</th>
              <th>จำนวน</th>
              <th>สถานะ</th>
              <th>สร้างเมื่อ</th>
              <th>จัดการ</th>
            </tr>
          </thead>
          <tbody>
            {charges.map((c) => (
              <Row key={c.id} c={c} open={openId === c.id} onToggle={() => setOpenId(openId === c.id ? null : c.id)} onVoid={doVoid} onRefund={doRefund} />
            ))}
            {charges.length === 0 && (
              <tr>
                <td colSpan={7} className="muted" style={{ textAlign: "center", padding: 28 }}>
                  ไม่มีรายการ
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <p className="muted" style={{ fontSize: 12, marginTop: 10 }}>API base: {API_URL}</p>
    </div>
  );
}

function Row({ c, open, onToggle, onVoid, onRefund }) {
  const expandable = (c.status === "paid" || c.status === "refunded") && c.payment;
  return (
    <>
      <tr>
        <td className="mono" onClick={expandable ? onToggle : undefined} style={{ cursor: expandable ? "pointer" : "default" }}>
          {expandable ? (open ? "▾ " : "▸ ") : ""}{c.id.slice(0, 14)}…
        </td>
        <td>{c.reference || "—"}</td>
        <td>{c.description || "—"}</td>
        <td>{baht(c.amount)}</td>
        <td><StatusBadge status={c.status} /></td>
        <td className="muted">{fmt(c.created_at)}</td>
        <td>
          <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
            <a href={`${window.location.origin}/pay/${c.id}`} target="_blank" rel="noreferrer">เปิด</a>
            {(c.status === "paid" || c.status === "refunded") && (
              <a href={receiptUrl(c.id)} target="_blank" rel="noreferrer">ใบเสร็จ</a>
            )}
            {c.status === "pending" && (
              <button className="btn danger" style={{ padding: "4px 10px" }} onClick={() => onVoid(c.id)}>ยกเลิก</button>
            )}
            {c.status === "paid" && (
              <button className="btn danger" style={{ padding: "4px 10px" }} onClick={() => onRefund(c.id)}>คืนเงิน</button>
            )}
          </div>
        </td>
      </tr>
      {open && expandable && (
        <tr>
          <td colSpan={7} style={{ paddingTop: 0 }}>
            <PaymentDetail charge={c} />
          </td>
        </tr>
      )}
    </>
  );
}
