import { Link } from "react-router-dom";
import Logo from "../components/Logo.jsx";

const FEATURES = [
  { ic: "🔳", t: "QR PromptPay ทันที", d: "สร้างลิงก์หรือ QR เรียกเก็บเงินได้ในไม่กี่วินาที ลูกค้าสแกนจ่ายผ่านแอปธนาคารไหนก็ได้" },
  { ic: "✅", t: "ตรวจสลิปอัตโนมัติ", d: "ลูกค้าแนบสลิป ระบบตรวจยอด ชื่อผู้รับ และสลิปซ้ำให้อัตโนมัติ รู้ผลทันที ไม่ต้องเช็คเอง" },
  { ic: "🏦", t: "ตรวจเงินเข้าอัตโนมัติ", d: "เชื่อมการแจ้งเตือนจากแอปธนาคาร ระบบตัดยอดและยืนยันการชำระให้เองโดยไม่ต้องแนบสลิป" },
  { ic: "📊", t: "แดชบอร์ดเรียลไทม์", d: "ดูยอดขาย รายการ และสถิติแบบสด ออกใบเสร็จ PDF และดาวน์โหลดรายงานได้ทันที" },
  { ic: "🔁", t: "ระบบสมาชิก & บิลรายเดือน", d: "เก็บค่าสมาชิก/Subscription ต่ออายุอัตโนมัติ พร้อมคูปองส่วนลดและพอร์ทัลให้ลูกค้าจัดการเอง" },
  { ic: "🔌", t: "API & Webhook", d: "เชื่อมเข้ากับเว็บหรือระบบ POS ของร้านคุณ รับแจ้งเตือนทันทีเมื่อชำระเงินสำเร็จหรือคืนเงิน" },
];

const STEPS = [
  { t: "สมัครและตั้งค่า", d: "เปิดบัญชีร้านค้า ใส่ PromptPay ของคุณ ใช้เวลาไม่ถึง 5 นาที" },
  { t: "สร้างรายการเรียกเก็บ", d: "สร้าง QR/ลิงก์จากแดชบอร์ด หรือเชื่อมผ่าน API ของระบบร้าน" },
  { t: "ลูกค้าสแกนจ่าย", d: "ลูกค้าจ่ายผ่าน PromptPay แนบสลิป หรือให้ระบบตรวจเงินเข้าเอง" },
  { t: "รับเงิน & ดูผลทันที", d: "เงินเข้าบัญชีร้านโดยตรง สถานะอัปเดตในแดชบอร์ดเรียลไทม์" },
];

const FAQ = [
  { q: "เงินเข้าบัญชีใคร?", a: "เงินเข้าบัญชี PromptPay ของร้านคุณโดยตรง PunPay ไม่ถือเงินของคุณ — เราเป็นเพียงระบบสร้าง QR และตรวจสอบการชำระเงินให้" },
  { q: "รองรับธนาคารไหนบ้าง?", a: "รองรับทุกธนาคารและทุกแอปที่ใช้ PromptPay ได้ ลูกค้าสแกน QR แล้วจ่ายจากแอปธนาคารที่ใช้อยู่ได้เลย" },
  { q: "ตรวจสลิปปลอมได้ไหม?", a: "ได้ ระบบตรวจสอบยอดเงิน ชื่อบัญชีผู้รับ และสลิปซ้ำผ่านผู้ให้บริการตรวจสลิปมาตรฐาน ช่วยลดความเสี่ยงสลิปปลอมและสลิปซ้ำ" },
  { q: "ต้องเขียนโปรแกรมไหม?", a: "ไม่จำเป็น ใช้งานผ่านแดชบอร์ดได้ทันที ถ้าต้องการเชื่อมกับระบบร้านของคุณก็มี API และ Webhook ให้ใช้" },
  { q: "คิดค่าบริการอย่างไร?", a: "เติมเครดิตล่วงหน้า แล้วหักตามจริงต่อรายการที่ชำระสำเร็จ ไม่มีค่าแรกเข้า ไม่มีค่ารายเดือน" },
];

function Brand() {
  return <Logo height={30} />;
}

export default function Landing() {
  return (
    <div className="lp">
      {/* NAV */}
      <header className="lp-nav">
        <div className="lp-wrap lp-nav-inner">
          <Brand />
          <nav className="lp-nav-links">
            <a href="#features">ฟีเจอร์</a>
            <a href="#how">วิธีใช้งาน</a>
            <a href="#pricing">ราคา</a>
            <a href="#faq">คำถามที่พบบ่อย</a>
          </nav>
          <div className="lp-nav-cta">
            <Link className="lp-btn ghost" to="/login">เข้าสู่ระบบ</Link>
            <Link className="lp-btn primary" to="/register">สมัครใช้งานฟรี</Link>
          </div>
        </div>
      </header>

      {/* HERO */}
      <section className="lp-hero">
        <div className="lp-wrap lp-hero-grid">
          <div>
            <span className="lp-eyebrow">⚡ ระบบรับชำระเงิน PromptPay สำหรับร้านค้า</span>
            <h1 className="lp-h1">
              รับเงินด้วย <span className="grad">PromptPay</span><br />
              ตรวจสลิปอัตโนมัติ รู้ผลทันที
            </h1>
            <p className="lp-lead">
              PunPay ช่วยร้านค้ารับชำระเงินออนไลน์ — สร้าง QR พร้อมเพย์ ตรวจสลิปและเงินเข้าอัตโนมัติ
              จัดการสมาชิกและบิลรายเดือน พร้อม API ครบในที่เดียว
            </p>
            <div className="lp-hero-cta">
              <Link className="lp-btn primary lg" to="/register">เริ่มใช้งานฟรี →</Link>
              <a className="lp-btn ghost lg" href="#how">ดูวิธีใช้งาน</a>
            </div>
            <div className="lp-hero-note">
              <span>✓ ไม่มีค่าแรกเข้า</span>
              <span>✓ เงินเข้าบัญชีร้านโดยตรง</span>
              <span>✓ ตั้งค่าได้ใน 5 นาที</span>
            </div>
          </div>

          <div className="lp-visual">
            <div className="lp-card">
              <div className="lp-card-top">
                <div>
                  <div className="muted" style={{ fontSize: 13 }}>ยอดชำระ</div>
                  <div className="amt">฿1,250.00</div>
                </div>
                <Brand />
              </div>
              <div className="lp-qr-wrap">
                <img className="lp-qr" src="/qr-demo.svg" alt="สแกนเพื่อชำระเงิน" />
              </div>
              <div className="lp-card-paid">
                <span className="dot">✓</span>
                ชำระเงินสำเร็จ · ตรวจสลิปอัตโนมัติแล้ว
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* TRUST */}
      <div className="lp-trust">
        <div className="lp-wrap lp-trust-inner">
          <span>รองรับ <b>PromptPay</b> ทุกธนาคาร</span>
          <span>ตรวจสลิปด้วย <b>Slip2Go</b></span>
          <span>ออก <b>ใบเสร็จ PDF</b></span>
          <span><b>API & Webhook</b> สำหรับนักพัฒนา</span>
        </div>
      </div>

      {/* FEATURES */}
      <section className="lp-section" id="features">
        <div className="lp-wrap">
          <div className="lp-kicker">ฟีเจอร์</div>
          <h2 className="lp-h2">ทุกอย่างที่ร้านค้าต้องใช้</h2>
          <p className="lp-sub">ตั้งแต่สร้าง QR รับเงิน ตรวจสลิป ไปจนถึงระบบสมาชิกและการเชื่อมต่อ API</p>
          <div className="lp-features">
            {FEATURES.map((f) => (
              <div className="lp-feature" key={f.t}>
                <div className="ic">{f.ic}</div>
                <h3>{f.t}</h3>
                <p>{f.d}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* HOW IT WORKS */}
      <section className="lp-section alt" id="how">
        <div className="lp-wrap">
          <div className="lp-kicker">วิธีใช้งาน</div>
          <h2 className="lp-h2">เริ่มรับเงินได้ใน 4 ขั้นตอน</h2>
          <p className="lp-sub">ไม่ต้องมีความรู้ด้านเทคนิค ใช้งานผ่านแดชบอร์ดได้ทันที</p>
          <div className="lp-steps">
            {STEPS.map((s, i) => (
              <div className="lp-step" key={s.t}>
                <div className="n">{i + 1}</div>
                <h3>{s.t}</h3>
                <p>{s.d}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* PRICING */}
      <section className="lp-section" id="pricing">
        <div className="lp-wrap">
          <div className="lp-kicker">ราคา</div>
          <h2 className="lp-h2">จ่ายตามที่ใช้จริง</h2>
          <p className="lp-sub">เติมเครดิตล่วงหน้า หักเฉพาะรายการที่ชำระสำเร็จ ไม่มีค่าใช้จ่ายแอบแฝง</p>
          <div className="lp-price">
            <span className="tag">โปรโมชั่น · ลด 50%</span>
            <div className="muted" style={{ fontWeight: 700, fontSize: 15, marginTop: 4 }}>ค่าบริการ</div>
            <div className="lp-price-row">
              <span className="lp-was">฿1.00</span>
              <span className="big" style={{ margin: 0 }}>฿0.50 <small>/ รายการ</small></span>
            </div>
            <div className="muted">ต่อรายการที่ชำระเงินสำเร็จ</div>
            <ul>
              <li>ไม่มีค่าแรกเข้า ไม่มีค่ารายเดือน</li>
              <li>เงินเข้าบัญชี PromptPay ของร้านโดยตรง</li>
              <li>ตรวจสลิป &amp; ตรวจเงินเข้าอัตโนมัติ</li>
              <li>ระบบสมาชิก บิลรายเดือน และคูปอง</li>
              <li>API, Webhook และใบเสร็จ PDF</li>
            </ul>
            <Link className="lp-btn primary lg" to="/register" style={{ width: "100%" }}>สมัครใช้งานฟรี</Link>
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section className="lp-section alt" id="faq">
        <div className="lp-wrap">
          <div className="lp-kicker">คำถามที่พบบ่อย</div>
          <h2 className="lp-h2">มีคำถาม?</h2>
          <p className="lp-sub">เรื่องที่ร้านค้าถามเรามากที่สุด</p>
          <div className="lp-faq">
            {FAQ.map((f) => (
              <details key={f.q}>
                <summary>{f.q}</summary>
                <p>{f.a}</p>
              </details>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="lp-section" style={{ paddingTop: 0 }}>
        <div className="lp-wrap">
          <div className="lp-cta">
            <h2>พร้อมเริ่มรับเงินแล้วหรือยัง?</h2>
            <p>สมัครฟรีวันนี้ แล้วเริ่มสร้าง QR รับชำระเงินได้ทันที</p>
            <Link className="lp-btn light lg" to="/register">เริ่มใช้งานฟรี →</Link>
          </div>
        </div>
      </section>

      {/* FOOTER */}
      <footer className="lp-footer">
        <div className="lp-wrap lp-footer-inner">
          <Brand />
          <div>© 2026 PunPay · ระบบรับชำระเงิน PromptPay สำหรับร้านค้า</div>
          <div style={{ display: "flex", gap: 18 }}>
            <Link to="/login">เข้าสู่ระบบ</Link>
            <Link to="/register">สมัครใช้งาน</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
