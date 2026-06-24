import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { adminApi } from "../api.js";

const baht = (n) => "฿" + Number(n).toLocaleString("th-TH", { minimumFractionDigits: 2 });
const fmtDate = (d) => (d ? new Date(d).toLocaleDateString("th-TH") : "—");

const SUB_LABELS = { pending: "รอชำระ", active: "ใช้งาน", past_due: "ครบกำหนด", expired: "หมดอายุ", canceled: "ยกเลิก" };
const SUB_BADGE = { pending: "pending", active: "paid", past_due: "refunded", expired: "expired", canceled: "canceled" };
const intervalText = (u, c) => `ทุก ${c > 1 ? c + " " : ""}${{ day: "วัน", month: "เดือน", year: "ปี" }[u]}`;

function Plans({ mid, plans, reload, onError }) {
  const [form, setForm] = useState({ name: "", amount: "", interval_unit: "month", interval_count: 1 });

  async function add(e) {
    e.preventDefault();
    try {
      await adminApi.mCreatePlan(mid, {
        name: form.name,
        amount: parseFloat(form.amount),
        interval_unit: form.interval_unit,
        interval_count: parseInt(form.interval_count) || 1,
      });
      setForm({ name: "", amount: "", interval_unit: "month", interval_count: 1 });
      reload();
    } catch (e) {
      onError(e.message);
    }
  }

  return (
    <div className="card">
      <strong>แผนสมาชิก</strong>
      <p className="muted" style={{ fontSize: 13 }}>แพ็กเกจที่ลูกค้าสมัครเป็นสมาชิกและจ่ายตามรอบ</p>
      <table style={{ marginTop: 6 }}>
        <tbody>
          {plans.map((p) => (
            <tr key={p.id}>
              <td>{p.name}{!p.active && <span className="badge canceled" style={{ marginLeft: 8 }}>ปิด</span>}</td>
              <td>{baht(p.amount)}</td>
              <td className="muted">{intervalText(p.interval_unit, p.interval_count)}</td>
              <td style={{ textAlign: "right" }}>
                {p.active && (
                  <button className="btn ghost" style={{ padding: "4px 10px", marginRight: 6 }}
                          onClick={() => adminApi.mUpdatePlan(mid, p.id, { active: false }).then(reload).catch((e) => onError(e.message))}>
                    ปิดใช้งาน
                  </button>
                )}
                <button className="btn danger" style={{ padding: "4px 10px" }}
                        onClick={() => adminApi.mDeletePlan(mid, p.id).then(reload).catch((e) => onError(e.message))}>
                  ลบ
                </button>
              </td>
            </tr>
          ))}
          {plans.length === 0 && <tr><td className="muted" style={{ padding: 12 }}>ยังไม่มีแผน</td></tr>}
        </tbody>
      </table>
      <form onSubmit={add} style={{ display: "flex", gap: 8, alignItems: "flex-end", marginTop: 12, flexWrap: "wrap" }}>
        <label className="field" style={{ flex: 2, marginBottom: 0, minWidth: 140 }}>
          <span className="lbl">ชื่อแผน</span>
          <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Gold" required />
        </label>
        <label className="field" style={{ flex: 1, marginBottom: 0, minWidth: 90 }}>
          <span className="lbl">ราคา (฿)</span>
          <input type="number" step="0.01" min="0.01" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} required />
        </label>
        <label className="field" style={{ marginBottom: 0, width: 70 }}>
          <span className="lbl">ทุก</span>
          <input type="number" min="1" value={form.interval_count} onChange={(e) => setForm({ ...form, interval_count: e.target.value })} />
        </label>
        <label className="field" style={{ marginBottom: 0, width: 110 }}>
          <span className="lbl">หน่วย</span>
          <select value={form.interval_unit} onChange={(e) => setForm({ ...form, interval_unit: e.target.value })}>
            <option value="day">วัน</option>
            <option value="month">เดือน</option>
            <option value="year">ปี</option>
          </select>
        </label>
        <button className="btn">เพิ่มแผน</button>
      </form>
    </div>
  );
}

const couponLabel = (c) => `${c.code} (${c.discount_type === "percent" ? c.value + "%" : baht(c.value)})`;

function NewMember({ mid, plans, coupons, reload, onError, onInvoice }) {
  const [form, setForm] = useState({ plan_id: "", customer_name: "", customer_email: "", customer_phone: "", customer_line_id: "", coupon_code: "" });
  const active = plans.filter((p) => p.active);

  async function add(e) {
    e.preventDefault();
    try {
      const res = await adminApi.mCreateSubscription(mid, {
        plan_id: form.plan_id || active[0]?.id,
        customer_name: form.customer_name,
        customer_email: form.customer_email || null,
        customer_phone: form.customer_phone || null,
        customer_line_id: form.customer_line_id || null,
        coupon_code: form.coupon_code || null,
      });
      setForm({ plan_id: "", customer_name: "", customer_email: "", customer_phone: "", customer_line_id: "", coupon_code: "" });
      onInvoice(res.invoice);
      reload();
    } catch (e) {
      onError(e.message);
    }
  }

  if (active.length === 0) return <p className="muted">สร้างแผนที่เปิดใช้งานก่อน จึงจะรับสมัครสมาชิกได้</p>;

  return (
    <form onSubmit={add} style={{ display: "flex", gap: 8, alignItems: "flex-end", flexWrap: "wrap" }}>
      <label className="field" style={{ flex: 1, marginBottom: 0, minWidth: 120 }}>
        <span className="lbl">ชื่อลูกค้า</span>
        <input value={form.customer_name} onChange={(e) => setForm({ ...form, customer_name: e.target.value })} required />
      </label>
      <label className="field" style={{ flex: 1, marginBottom: 0, minWidth: 130 }}>
        <span className="lbl">อีเมล</span>
        <input type="email" value={form.customer_email} onChange={(e) => setForm({ ...form, customer_email: e.target.value })} />
      </label>
      <label className="field" style={{ marginBottom: 0, width: 120 }}>
        <span className="lbl">เบอร์โทร</span>
        <input value={form.customer_phone} onChange={(e) => setForm({ ...form, customer_phone: e.target.value })} placeholder="08x" />
      </label>
      <label className="field" style={{ marginBottom: 0, width: 120 }}>
        <span className="lbl">LINE ID</span>
        <input value={form.customer_line_id} onChange={(e) => setForm({ ...form, customer_line_id: e.target.value })} placeholder="Uxxxx" />
      </label>
      <label className="field" style={{ marginBottom: 0, minWidth: 150 }}>
        <span className="lbl">แผน</span>
        <select value={form.plan_id} onChange={(e) => setForm({ ...form, plan_id: e.target.value })}>
          {active.map((p) => <option key={p.id} value={p.id}>{p.name} — {baht(p.amount)}</option>)}
        </select>
      </label>
      <label className="field" style={{ marginBottom: 0, width: 150 }}>
        <span className="lbl">คูปอง</span>
        <select value={form.coupon_code} onChange={(e) => setForm({ ...form, coupon_code: e.target.value })}>
          <option value="">— ไม่ใช้ —</option>
          {coupons.filter((c) => c.active).map((c) => (
            <option key={c.id} value={c.code}>{couponLabel(c)}</option>
          ))}
        </select>
      </label>
      <button className="btn">รับสมัคร + ออกบิล</button>
    </form>
  );
}

function Coupons({ mid, coupons, reload, onError }) {
  const [form, setForm] = useState({ code: "", discount_type: "percent", value: "", duration: "once" });

  async function add(e) {
    e.preventDefault();
    try {
      await adminApi.mCreateCoupon(mid, {
        code: form.code,
        discount_type: form.discount_type,
        value: parseFloat(form.value),
        duration: form.duration,
      });
      setForm({ code: "", discount_type: "percent", value: "", duration: "once" });
      reload();
    } catch (e) {
      onError(e.message);
    }
  }

  return (
    <div className="card">
      <strong>คูปอง / ส่วนลด</strong>
      <p className="muted" style={{ fontSize: 13 }}>ใช้ตอนรับสมัครสมาชิก (ครั้งแรก หรือ ทุกบิล)</p>
      <table style={{ marginTop: 6 }}>
        <tbody>
          {coupons.map((c) => (
            <tr key={c.id}>
              <td className="mono">{c.code}{!c.active && <span className="badge canceled" style={{ marginLeft: 8 }}>ปิด</span>}</td>
              <td>{c.discount_type === "percent" ? `${c.value}%` : baht(c.value)}</td>
              <td className="muted">{c.duration === "forever" ? "ทุกบิล" : "ครั้งแรก"}</td>
              <td className="muted">ใช้ไป {c.times_redeemed}{c.max_redemptions ? `/${c.max_redemptions}` : ""}</td>
              <td style={{ textAlign: "right" }}>
                {c.active && (
                  <button className="btn danger" style={{ padding: "4px 10px" }}
                          onClick={() => adminApi.mDeleteCoupon(mid, c.id).then(reload).catch((e) => onError(e.message))}>
                    ปิด
                  </button>
                )}
              </td>
            </tr>
          ))}
          {coupons.length === 0 && <tr><td className="muted" style={{ padding: 12 }}>ยังไม่มีคูปอง</td></tr>}
        </tbody>
      </table>
      <form onSubmit={add} style={{ display: "flex", gap: 8, alignItems: "flex-end", marginTop: 12, flexWrap: "wrap" }}>
        <label className="field" style={{ marginBottom: 0, width: 130 }}>
          <span className="lbl">โค้ด</span>
          <input value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} placeholder="SAVE20" required />
        </label>
        <label className="field" style={{ marginBottom: 0, width: 110 }}>
          <span className="lbl">ประเภท</span>
          <select value={form.discount_type} onChange={(e) => setForm({ ...form, discount_type: e.target.value })}>
            <option value="percent">เปอร์เซ็นต์</option>
            <option value="fixed">บาท</option>
          </select>
        </label>
        <label className="field" style={{ marginBottom: 0, width: 90 }}>
          <span className="lbl">ค่า</span>
          <input type="number" step="0.01" min="0.01" value={form.value} onChange={(e) => setForm({ ...form, value: e.target.value })} required />
        </label>
        <label className="field" style={{ marginBottom: 0, width: 110 }}>
          <span className="lbl">ใช้</span>
          <select value={form.duration} onChange={(e) => setForm({ ...form, duration: e.target.value })}>
            <option value="once">ครั้งแรก</option>
            <option value="forever">ทุกบิล</option>
          </select>
        </label>
        <button className="btn">เพิ่มคูปอง</button>
      </form>
    </div>
  );
}

export default function AdminMerchantMembers() {
  const { id: mid } = useParams();
  const [merchant, setMerchant] = useState(null);
  const [plans, setPlans] = useState([]);
  const [subs, setSubs] = useState([]);
  const [stats, setStats] = useState(null);
  const [coupons, setCoupons] = useState([]);
  const [notifs, setNotifs] = useState([]);
  const [err, setErr] = useState("");
  const [invoice, setInvoice] = useState(null);
  const [changing, setChanging] = useState(null);

  async function load() {
    try {
      const [m, p, s, st, c, n] = await Promise.all([
        adminApi.merchant(mid), adminApi.mPlans(mid), adminApi.mSubscriptions(mid),
        adminApi.mSubscriptionStats(mid), adminApi.mCoupons(mid), adminApi.mNotifications(mid),
      ]);
      setMerchant(m);
      setPlans(p);
      setSubs(s);
      setStats(st);
      setCoupons(c);
      setNotifs(n.slice(0, 8));
    } catch (e) {
      setErr(e.message);
    }
  }
  useEffect(() => { load(); }, [mid]);

  async function submitChangePlan() {
    try {
      const detail = await adminApi.mChangePlan(mid, changing.sub.id, changing.planId);
      const proration = (detail.invoices || []).find((c) => (c.metadata || {}).proration && c.status === "pending");
      if (proration) setInvoice(proration);
      setChanging(null);
      load();
    } catch (e) {
      setErr(e.message);
    }
  }

  async function renew(id) {
    try {
      const inv = await adminApi.mRenewSubscription(mid, id);
      setInvoice(inv);
      load();
    } catch (e) {
      setErr(e.message);
    }
  }
  async function cancel(id) {
    if (!confirm("ยกเลิกสมาชิกรายนี้?")) return;
    try {
      await adminApi.mCancelSubscription(mid, id);
      load();
    } catch (e) {
      setErr(e.message);
    }
  }
  async function generateDue() {
    try {
      const inv = await adminApi.mGenerateDue(mid);
      setErr("");
      alert(`สร้างบิลต่ออายุ ${inv.length} รายการ`);
      load();
    } catch (e) {
      setErr(e.message);
    }
  }

  return (
    <div>
      <p style={{ marginBottom: 6 }}>
        <Link to="/merchants">← ร้านค้าทั้งหมด</Link>
        {merchant && <> · <Link to={`/merchants/${mid}`}>{merchant.business_name}</Link></>}
      </p>
      <h1 className="page-title">สมาชิก / Subscription</h1>
      <p className="page-sub">
        {merchant ? `จัดการสมาชิกของร้าน "${merchant.business_name}"` : "กำลังโหลด…"} — แผนสมาชิกแบบจ่ายตามรอบผ่าน PromptPay
      </p>
      {err && <div className="error">{err}</div>}

      {stats && (
        <div className="grid cols-4" style={{ marginBottom: 16 }}>
          <div className="card">
            <div className="stat-label">MRR (รายได้ประจำ/เดือน)</div>
            <div className="stat-value green">{baht(stats.mrr)}</div>
            <div className="muted" style={{ fontSize: 12 }}>ARR {baht(stats.arr)}</div>
          </div>
          <div className="card">
            <div className="stat-label">สมาชิกใช้งาน</div>
            <div className="stat-value">{stats.active_members}</div>
          </div>
          <div className="card">
            <div className="stat-label">สมาชิกใหม่เดือนนี้</div>
            <div className="stat-value">{stats.new_this_month}</div>
          </div>
          <div className="card">
            <div className="stat-label">Churn เดือนนี้</div>
            <div className="stat-value">{stats.churn_rate}%</div>
            <div className="muted" style={{ fontSize: 12 }}>เลิก {stats.churned_this_month} ราย</div>
          </div>
        </div>
      )}

      {invoice && (
        <div className="card" style={{ marginBottom: 16, borderColor: "#c7d2fe" }}>
          <div className="notice" style={{ marginBottom: 8 }}>ออกบิลแล้ว — ส่งลิงก์นี้ให้ลูกค้าชำระเงิน ({baht(invoice.amount)})</div>
          <input readOnly className="mono" value={invoice.checkout_url} onFocus={(e) => e.target.select()} />
          <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
            <a className="btn" href={invoice.checkout_url} target="_blank" rel="noreferrer">เปิดหน้าชำระเงิน</a>
            <button className="btn ghost" onClick={() => setInvoice(null)}>ปิด</button>
          </div>
        </div>
      )}

      {changing && (
        <div className="card" style={{ marginBottom: 16, borderColor: "#c7d2fe" }}>
          <strong>เปลี่ยนแผนของ {changing.sub.customer_name}</strong>
          <div style={{ display: "flex", gap: 8, alignItems: "flex-end", marginTop: 10 }}>
            <label className="field" style={{ marginBottom: 0, minWidth: 220 }}>
              <span className="lbl">แผนใหม่</span>
              <select value={changing.planId} onChange={(e) => setChanging({ ...changing, planId: e.target.value })}>
                {plans.filter((p) => p.active && p.id !== changing.sub.plan_id).map((p) => (
                  <option key={p.id} value={p.id}>{p.name} — {baht(p.amount)}</option>
                ))}
              </select>
            </label>
            <button className="btn" onClick={submitChangePlan} disabled={!changing.planId}>ยืนยันเปลี่ยนแผน</button>
            <button className="btn ghost" onClick={() => setChanging(null)}>ยกเลิก</button>
          </div>
          <p className="muted" style={{ fontSize: 12, marginTop: 8 }}>
            อัปเกรดจะออกบิลส่วนต่างตามสัดส่วนเวลาที่เหลือ · ดาวน์เกรดราคาใหม่จะมีผลรอบถัดไป
          </p>
        </div>
      )}

      <div className="grid cols-2" style={{ marginBottom: 16 }}>
        <Plans mid={mid} plans={plans} reload={load} onError={setErr} />
        <Coupons mid={mid} coupons={coupons} reload={load} onError={setErr} />
      </div>

      <div className="card">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
          <strong>สมาชิก ({subs.length})</strong>
          <button className="btn ghost" onClick={generateDue}>สร้างบิลครบกำหนด</button>
        </div>
        <NewMember mid={mid} plans={plans} coupons={coupons} reload={load} onError={setErr} onInvoice={setInvoice} />
        <table style={{ marginTop: 14 }}>
          <thead>
            <tr><th>ลูกค้า</th><th>แผน</th><th>สถานะ</th><th>ครบกำหนด</th><th>จัดการ</th></tr>
          </thead>
          <tbody>
            {subs.map((s) => (
              <tr key={s.id}>
                <td>{s.customer_name}{s.customer_email && <div className="muted" style={{ fontSize: 12 }}>{s.customer_email}</div>}</td>
                <td>{s.plan_name}</td>
                <td><span className={`badge ${SUB_BADGE[s.status]}`}>{SUB_LABELS[s.status] || s.status}</span></td>
                <td className="muted">{fmtDate(s.current_period_end)}</td>
                <td>
                  <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                    {s.portal_url && (
                      <a href={s.portal_url} target="_blank" rel="noreferrer" title="ลิงก์สำหรับสมาชิก">ลิงก์สมาชิก</a>
                    )}
                    {s.status !== "canceled" && (
                      <button className="btn ghost" style={{ padding: "4px 10px" }} onClick={() => renew(s.id)}>ออกบิล</button>
                    )}
                    {!["canceled", "expired"].includes(s.status) && (
                      <button className="btn ghost" style={{ padding: "4px 10px" }}
                              onClick={() => setChanging({ sub: s, planId: plans.find((p) => p.active && p.id !== s.plan_id)?.id || "" })}>
                        เปลี่ยนแผน
                      </button>
                    )}
                    {s.status !== "canceled" && (
                      <button className="btn danger" style={{ padding: "4px 10px" }} onClick={() => cancel(s.id)}>ยกเลิก</button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
            {subs.length === 0 && <tr><td colSpan={5} className="muted" style={{ textAlign: "center", padding: 24 }}>ยังไม่มีสมาชิก</td></tr>}
          </tbody>
        </table>
      </div>

      {notifs.length > 0 && (
        <div className="card" style={{ marginTop: 16 }}>
          <strong>การแจ้งเตือนล่าสุด</strong>
          <table style={{ marginTop: 8 }}>
            <tbody>
              {notifs.map((n) => (
                <tr key={n.id}>
                  <td className="muted" style={{ fontSize: 12 }}>{new Date(n.created_at).toLocaleString("th-TH")}</td>
                  <td>{({ email: "📧", sms: "💬", line: "🟢 LINE" }[n.channel]) || n.channel} {n.recipient}</td>
                  <td className="muted">{n.event === "invoice.issued" ? "แจ้งบิล" : "แจ้งรับชำระ"}</td>
                  <td style={{ textAlign: "right" }}>
                    <span className={`badge ${n.status === "sent" ? "paid" : n.status === "failed" ? "refunded" : "canceled"}`}>
                      {{ sent: "ส่งแล้ว", failed: "ล้มเหลว", skipped: "บันทึก (ยังไม่ตั้งค่าส่งจริง)" }[n.status] || n.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
