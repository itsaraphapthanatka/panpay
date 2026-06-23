import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../api.js";

const baht = (n) => "฿" + Number(n).toLocaleString("th-TH", { minimumFractionDigits: 2 });
const fmtDate = (d) => (d ? new Date(d).toLocaleDateString("th-TH") : "—");
const intervalText = (u, c) => (u ? `ทุก ${c > 1 ? c + " " : ""}${{ day: "วัน", month: "เดือน", year: "ปี" }[u]}` : "");

const STATUS = {
  pending: { label: "รอชำระเงิน", cls: "pending" },
  active: { label: "ใช้งาน", cls: "paid" },
  past_due: { label: "ครบกำหนดชำระ", cls: "refunded" },
  expired: { label: "หมดอายุ", cls: "expired" },
  canceled: { label: "ยกเลิกแล้ว", cls: "canceled" },
};

export default function Portal() {
  const { token } = useParams();
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  async function load() {
    try {
      setData(await api.portalView(token));
    } catch (e) {
      setErr(e.message);
    }
  }
  useEffect(() => {
    load();
  }, [token]);

  async function payOrRenew() {
    setBusy(true);
    setErr("");
    try {
      if (data.open_invoice_url) {
        window.location.assign(data.open_invoice_url);
      } else {
        const { checkout_url } = await api.portalRenew(token);
        window.location.assign(checkout_url);
      }
    } catch (e) {
      setErr(e.message);
      setBusy(false);
    }
  }

  if (!data) {
    return (
      <div className="pay-wrap">
        <div className="pay-card">
          <div className="pay-body">{err ? <div className="error">{err}</div> : "กำลังโหลด…"}</div>
        </div>
      </div>
    );
  }

  const st = STATUS[data.status] || { label: data.status, cls: "pending" };
  const canPay = data.status !== "canceled";

  return (
    <div className="pay-wrap">
      <div className="pay-card" style={{ maxWidth: 460 }}>
        <div className="pay-head">
          <div style={{ opacity: 0.85, fontSize: 13 }}>{data.business_name}</div>
          <div style={{ fontSize: 18, fontWeight: 800, marginTop: 4 }}>สถานะสมาชิก</div>
        </div>
        <div className="pay-body" style={{ textAlign: "left" }}>
          {err && <div className="error">{err}</div>}

          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
            <div>
              <div style={{ fontWeight: 700 }}>{data.customer_name}</div>
              <div className="muted" style={{ fontSize: 13 }}>
                {data.plan_name} · {baht(data.plan_amount)} {intervalText(data.interval_unit, data.interval_count)}
              </div>
            </div>
            <span className={`badge ${st.cls}`}>{st.label}</span>
          </div>

          <div style={{ background: "var(--surface-2)", borderRadius: 12, padding: 14, fontSize: 14, marginBottom: 16 }}>
            {data.status === "active" ? (
              <>ใช้งานได้ถึง <b>{fmtDate(data.current_period_end)}</b></>
            ) : data.status === "canceled" ? (
              <>สมาชิกถูกยกเลิกแล้ว</>
            ) : (
              <>กรุณาชำระเงินเพื่อ{data.status === "pending" ? "เริ่มใช้งาน" : "ต่ออายุ"}สมาชิก</>
            )}
          </div>

          {canPay && (
            <button className="btn block" onClick={payOrRenew} disabled={busy}>
              {busy ? "กำลังเปิดหน้าชำระเงิน…" : data.open_invoice_url ? "ชำระบิลที่ค้าง" : "ต่ออายุสมาชิก"}
            </button>
          )}

          <div style={{ marginTop: 20 }}>
            <div className="muted" style={{ fontSize: 13, marginBottom: 8 }}>ประวัติการชำระเงิน</div>
            <table>
              <tbody>
                {data.invoices.map((c) => (
                  <tr key={c.id}>
                    <td className="muted" style={{ fontSize: 12 }}>{fmtDate(c.created_at)}</td>
                    <td>{baht(c.amount)}</td>
                    <td style={{ textAlign: "right" }}>
                      <span className={`badge ${c.status}`}>
                        {{ paid: "ชำระแล้ว", pending: "รอชำระ", expired: "หมดอายุ", canceled: "ยกเลิก", refunded: "คืนเงิน" }[c.status] || c.status}
                      </span>
                    </td>
                  </tr>
                ))}
                {data.invoices.length === 0 && <tr><td className="muted" style={{ padding: 10 }}>ยังไม่มีบิล</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
