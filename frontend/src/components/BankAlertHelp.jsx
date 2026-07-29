// Collapsible how-tos for connecting a bank's LINE "money in" alert service so the
// LINE account the bot logs into receives notifications the bot can read.
function Bank({ title, oaId, steps, note }) {
  return (
    <details style={{ marginTop: 8 }}>
      <summary style={{ cursor: "pointer", fontSize: 13, fontWeight: 600 }}>{title}</summary>
      <div className="muted" style={{ fontSize: 13, marginTop: 8, lineHeight: 1.7 }}>
        <ol style={{ margin: 0, paddingLeft: 18 }}>
          <li>
            เปิดแอป <strong>LINE</strong> (บัญชีเดียวกับที่จะเชื่อมบอท) → ค้นหา
            <span className="mono"> {oaId} </span> → กด <strong>เพิ่มเพื่อน</strong>
          </li>
          {steps.map((s, i) => <li key={i} dangerouslySetInnerHTML={{ __html: s }} />)}
        </ol>
        {note && <p style={{ margin: "8px 0 0" }}>{note}</p>}
      </div>
    </details>
  );
}

export default function BankAlertHelp() {
  return (
    <div className="bank-help" style={{ marginTop: 14 }}>
      <div style={{ fontSize: 13, fontWeight: 600 }}>ℹ️ วิธีสมัคร/เชื่อมแจ้งเตือนเงินเข้าใน LINE</div>
      <p className="muted" style={{ fontSize: 12, margin: "4px 0 6px" }}>
        บอทยืนยันเงินเข้าได้ ก็ต่อเมื่อ <strong>บัญชี LINE ที่ใช้เชื่อมบอท</strong> ได้รับการ์ด/ข้อความ
        “เงินเข้า” จากธนาคาร — ทำตามธนาคารของคุณก่อนสแกน QR เชื่อมบอท
      </p>

      <Bank
        title="🟢 KBank Live (กสิกรไทย)"
        oaId="@kbanklive"
        steps={[
          'เปิดแชท KBank Live → กด <strong>“ลงทะเบียน”</strong> → ยืนยันตัวตนด้วยแอป <strong>K PLUS</strong> หรือบัตรเดบิต/เลขบัญชี + เบอร์มือถือที่ผูกกับธนาคาร',
          'เปิดการแจ้งเตือน <strong>“รายการเงินเข้า/เดินบัญชี”</strong> (ปกติเปิดอัตโนมัติหลังลงทะเบียน)',
          'ทดสอบโอนเข้าบัญชีเล็กน้อย → ต้องเห็นการ์ด <strong>“รายการเงินเข้า”</strong> เด้งในแชท',
        ]}
      />

      <Bank
        title="🟩 BAAC Family (ธ.ก.ส.)"
        oaId="@baacfamily"
        steps={[
          'ในแชท BAAC Family → กด <strong>“ลงทะเบียน”</strong> สมัครบริการแจ้งเตือน (BAAC Connect) โดยยืนยันตัวตนด้วยแอป <strong>ธ.ก.ส. A-Mobile</strong> หรือเลขบัญชี/บัตร ATM + เบอร์มือถือ + OTP (บางกรณีต้องลงทะเบียนผ่าน A-Mobile หรือที่สาขา)',
          'เปิดบริการแจ้งเตือน <strong>“เงินเข้า/เดินบัญชี”</strong>',
          'ทดสอบโอนเข้าบัญชีเล็กน้อย → ต้องเห็นข้อความ/การ์ดแจ้งเงินเข้าในแชท BAAC Family',
        ]}
        note={
          <>
            หมายเหตุ: รูปแบบแจ้งเตือนของแต่ละธนาคารต่างกัน — ถ้าเชื่อมแล้วบอทยัง<strong>ไม่จับยอด</strong>ให้
            ส่งตัวอย่างข้อความแจ้งเตือนของ BAAC มา จะได้ปรับตัวอ่าน (parser) ให้รองรับ
          </>
        }
      />

      <p className="muted" style={{ fontSize: 12, margin: "10px 0 0" }}>
        ⚠️ ต้องทำในบัญชี LINE <strong>เดียวกับที่เชื่อมบอท</strong> ไม่งั้นบอทจะไม่เห็นการแจ้งเตือน •
        ขั้นตอนอาจต่างเล็กน้อยตามเวอร์ชันแอป ให้ทำตามที่ OA ของธนาคารแนะนำในแชท
      </p>
    </div>
  );
}
