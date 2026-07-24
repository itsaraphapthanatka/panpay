# PanPay LINE Balance Bot

LINE SelfBot (สร้างด้วย [`@evex/linejs`](https://github.com/evex-dev/linejs)) ที่ตอบ
**ยอดเงินคงเหลือของ merchant** เมื่อมีคนพิมพ์ `ยอดเงิน` / `balance` เข้ามาในแชท
โดยดึงยอดจาก backend ของ PanPay

> ⚠️ **คำเตือนสำคัญ**
> นี่คือ *SelfBot* — มันล็อกอินด้วย **บัญชี LINE ผู้ใช้จริง** ซึ่ง **ผิด LINE Terms of Service**
> และมีความเสี่ยงที่บัญชีจะโดนแบน/โดน logout เอง (เราเจอ `V3_TOKEN_CLIENT_LOGGED_OUT` มาแล้ว)
> ควรใช้กับบัญชีที่ยอมรับความเสี่ยงได้เท่านั้น
> **สำหรับ production แนะนำให้ใช้ LINE Messaging API official** (`backend/app/routers/line.py`)

---

## สถาปัตยกรรม

```
คนพิมพ์ "ยอดเงิน" ในแชท LINE
        │
        ▼
balance-bot.mjs  (@evex/linejs SelfBot, Node)
        │  GET /v1/balance  (Header: X-API-Key: sk_...)
        ▼
PanPay backend  (FastAPI)  ── อ่าน Merchant.balance ──▶ ตอบกลับเป็น JSON
        │
        ▼
บอทตอบยอดเงินกลับเข้าแชท
```

- **ยอดเงินมาจาก PanPay** ไม่ได้มาจาก LINE — `@evex/linejs` ไม่มีฟีเจอร์เงิน/LINE Pay ใด ๆ
  มันเป็นแค่ช่องทางรับส่งแชทเท่านั้น
- Endpoint ที่ใช้: `GET /v1/balance` (เพิ่มไว้ที่ `backend/app/routers/topup.py`)
  ใช้ **API key แบบไม่หมดอายุ** (`sk_...`) แทน JWT dashboard ที่หมดอายุเร็ว

---

## การติดตั้ง

ต้องมี **Node.js >= 20** (ทดสอบบน v24)

```bash
cd linebot
npm install
cp .env.example .env
```

`@evex/linejs` เผยแพร่บน **JSR** ไม่ใช่ npm ปกติ — ไฟล์ `.npmrc` ในโฟลเดอร์นี้
ตั้ง scope `@jsr` ให้ชี้ไป `https://npm.jsr.io` อยู่แล้ว จึง `npm install` ได้ตรง ๆ

---

## ตั้งค่า `.env`

| ตัวแปร | คำอธิบาย |
|---|---|
| `PANPAY_API_BASE` | base URL ของ backend เช่น `https://punpay.petgo.asia` (ไม่ต้องมี `/` ท้าย) |
| `PANPAY_API_KEY`  | secret key ของ merchant ขึ้นต้นด้วย `sk_` (สร้างในหน้า dashboard) |
| `ALLOWED_LINE_IDS` | (ไม่บังคับ) userId ของ LINE ที่อนุญาตให้ถามได้ คั่นด้วย `,` — เว้นว่าง = ตอบทุกคน (ไม่แนะนำ) |

---

## การรัน

```bash
node balance-bot.mjs
# หรือ
npm start
```

**ครั้งแรก** จะแสดง **QR code** ในเทอร์มินัล:

1. เปิดแอป **LINE บนมือถือ** (บัญชีที่จะให้เป็นบอท) → ปุ่มสแกน QR
2. สแกน QR ในจอ (อย่าเปิด URL ในเบราว์เซอร์ — มันจะ redirect ไป line.me เฉย ๆ)
3. เทอร์มินัลจะพิมพ์ **PIN** → ใส่เลขนั้นในแอป LINE
4. สำเร็จ → auth token ถูก cache ไว้ใน `storage.json` (ครั้งต่อไปไม่ต้องสแกน)

---

## การทดสอบ

### ทดสอบ endpoint อย่างเดียว (ไม่ต้องผ่าน LINE)

```bash
curl -H "X-API-Key: $(grep PANPAY_API_KEY .env | cut -d= -f2)" \
     "$(grep PANPAY_API_BASE .env | cut -d= -f2)/v1/balance"
```

ควรได้ `{"balance": ..., "credit_per_transaction": ..., "entries": [...]}`

### ทดสอบผ่าน LINE

- บอท = **บัญชีที่คุณสแกน QR** — มันเห็นเฉพาะข้อความที่ **คนอื่น** ส่งมา
- ใช้ **บัญชี LINE อีกตัว** (หรือให้เพื่อน / ในกลุ่ม) ทักหาบัญชีบอทแล้วพิมพ์ `ยอดเงิน`
- ส่งจากเครื่องบัญชีบอทเองไม่ได้ (บอทไม่เห็นข้อความขาออกของตัวเอง)
- คำที่ทริกเกอร์: `ยอดเงิน`, `ยอด`, `balance`, `/balance`

---

## แก้ปัญหาที่พบบ่อย

| อาการ | สาเหตุ / วิธีแก้ |
|---|---|
| `Missing PANPAY_API_BASE or PANPAY_API_KEY` | ยังไม่ได้สร้าง/กรอก `.env` |
| `404` ตอนเรียก `/v1/balance` | backend ยังไม่ได้ restart หลังเพิ่ม endpoint — restart uvicorn |
| `401 Missing API key` | `PANPAY_API_KEY` ไม่ได้ขึ้นต้น `sk_` หรือ key ผิด |
| `V3_TOKEN_CLIENT_LOGGED_OUT` / `NOT_AUTHORIZED_DEVICE` | token cache หมดอายุ/ถูก logout — สคริปต์จะล้างแล้วขึ้น QR ใหม่อัตโนมัติ (หรือลบ `storage.json` เองแล้วรันใหม่) |
| บอทเงียบไม่ตอบ | ดู log: ถ้ามี `Ignoring balance query from non-allowlisted id: <id>` ให้เอา id ไปใส่ `ALLOWED_LINE_IDS` หรือเว้นว่างตอนทดสอบ |

---

## ไฟล์ในโฟลเดอร์นี้

| ไฟล์ | หน้าที่ |
|---|---|
| `balance-bot.mjs` | ตัวบอทหลัก |
| `package.json` | dependencies (`@evex/linejs`, `qrcode-terminal`) |
| `.npmrc` | ชี้ scope `@jsr` ไปที่ JSR registry |
| `.env.example` | ตัวอย่างค่า config |
| `.env` | ค่าจริง (อยู่ใน `.gitignore`) |
| `storage.json` | auth token ที่ cache ไว้ (อยู่ใน `.gitignore`) |
