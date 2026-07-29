// Collapsible how-to for connecting KBank Live so the LINE account receives
// "money in" notifications the bot can read. Shown inside the LINE Bot cards.
export default function KBankLiveHelp() {
  return (
    <details className="kbank-help" style={{ marginTop: 14 }}>
      <summary style={{ cursor: "pointer", fontSize: 13, fontWeight: 600 }}>
        ℹ️ วิธีสมัคร/เชื่อม KBank Live เพื่อรับแจ้งเตือนเงินเข้าใน LINE
      </summary>
      <div className="muted" style={{ fontSize: 13, marginTop: 10, lineHeight: 1.7 }}>
        <p style={{ margin: "0 0 8px" }}>
          บอทยืนยันเงินเข้าได้ ก็ต่อเมื่อ <strong>บัญชี LINE ที่ใช้เชื่อมบอท</strong> ได้รับการ์ด
          “รายการเงินเข้า” จาก KBank Live — ทำตามนี้ก่อนสแกน QR เชื่อมบอท:
        </p>
        <ol style={{ margin: 0, paddingLeft: 18 }}>
          <li>
            เปิดแอป <strong>LINE</strong> (บัญชีเดียวกับที่จะเชื่อมบอท) → ค้นหา
            <span className="mono"> @kbanklive </span> หรือคำว่า “KBank Live” → กด
            <strong> เพิ่มเพื่อน</strong>
          </li>
          <li>
            เปิดแชท KBank Live → กด <strong>“ลงทะเบียน”</strong> แล้วยืนยันตัวตนด้วยแอป
            <strong> K PLUS</strong> หรือบัตรเดบิต/เลขบัญชี + เบอร์มือถือที่ผูกกับธนาคาร ตามขั้นตอนในแชท
          </li>
          <li>
            เลือกเปิดการแจ้งเตือน <strong>“รายการเงินเข้า/เดินบัญชี”</strong> (โดยปกติเปิดให้อัตโนมัติหลังลงทะเบียน)
          </li>
          <li>
            ทดสอบโอนเข้าบัญชีเล็กน้อย → ต้องเห็นการ์ด <strong>“รายการเงินเข้า”</strong> เด้งในแชท KBank Live
          </li>
        </ol>
        <p style={{ margin: "8px 0 0" }}>
          ⚠️ ต้องทำในบัญชี LINE <strong>เดียวกับที่เชื่อมบอท</strong> ไม่งั้นบอทจะไม่เห็นการแจ้งเตือน •
          ขั้นตอนอาจต่างเล็กน้อยตามเวอร์ชันแอป ให้ทำตามที่ KBank Live แนะนำในแชท
        </p>
      </div>
    </details>
  );
}
