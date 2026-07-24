import { test } from "node:test";
import assert from "node:assert/strict";
import { parseTransfer, parseMessage, parseFlexTransfer, extractFlexTexts } from "./parser.mjs";

test("parses SCB-style with thousands separator", () => {
  assert.equal(parseTransfer("มีเงินเข้าบัญชี x123 จำนวน 1,234.56 บาท").amount, 1234.56);
});

test("parses transfer received", () => {
  assert.equal(parseTransfer("บัญชี xxx รับโอนเงิน 500.00 บาท จากคุณสมชาย").amount, 500);
});

test("parses English received THB", () => {
  assert.equal(parseTransfer("You received THB 250.00 to your account").amount, 250);
});

test("parses ฿ prefix", () => {
  assert.equal(parseTransfer("เงินเข้า ฿1,000").amount, 1000);
});

test("ignores withdrawals", () => {
  assert.equal(parseTransfer("ถอนเงิน 300.00 บาท"), null);
});

test("ignores balance-only messages", () => {
  assert.equal(parseTransfer("ยอดเงินคงเหลือ 10,000.00 บาท"), null);
});

test("ignores non-money chatter", () => {
  assert.equal(parseTransfer("สวัสดีครับ พรุ่งนี้ว่างไหม"), null);
});

test("handles empty/garbage", () => {
  assert.equal(parseTransfer(""), null);
  assert.equal(parseTransfer(null), null);
  assert.equal(parseTransfer("เงินเข้า แต่ไม่มีตัวเลข"), null);
});

test("plain-text withdrawal keyword is rejected even with credit words", () => {
  assert.equal(parseTransfer("รายการโอน/ถอน เงินเข้า 1.00 บาท"), null);
});

// ---- Flex/card messages (KBank Live-style) ----

// Mirrors the real KBank Live card: [label, value] text pairs, with the
// transaction amount under "จำนวนเงิน" and the account balance under
// "ยอดเงินคงเหลือ" — the parser must pick the former, never the latter.
const kbankFlex = (header, accountLabel, amountText, balanceText) => ({
  contentType: "FLEX",
  contentMetadata: {
    FLEX_JSON: JSON.stringify({
      contents: [{
        body: {
          contents: [
            { type: "text", text: header },
            { type: "text", text: "24 ก.ค. 69 21:18 น." },
            { type: "box", contents: [
              { type: "text", text: accountLabel },
              { type: "text", text: "xxx-x-x5524-x" },
            ] },
            { type: "box", contents: [
              { type: "text", text: "จำนวนเงิน" },
              { type: "text", text: amountText },
            ] },
            { type: "box", contents: [
              { type: "text", text: "ยอดเงินคงเหลือ" },
              { type: "text", text: balanceText },
            ] },
          ],
        },
      }],
    }),
  },
});

test("extractFlexTexts collects text nodes in order", () => {
  const flex = JSON.parse(kbankFlex("รายการเงินเข้า", "เข้าบัญชี", "1.00 บาท", "11.67 บาท").contentMetadata.FLEX_JSON);
  assert.deepEqual(extractFlexTexts(flex), [
    "รายการเงินเข้า", "24 ก.ค. 69 21:18 น.",
    "เข้าบัญชี", "xxx-x-x5524-x",
    "จำนวนเงิน", "1.00 บาท",
    "ยอดเงินคงเหลือ", "11.67 บาท",
  ]);
});

test("flex money-in: takes จำนวนเงิน, not the balance", () => {
  const msg = kbankFlex("รายการเงินเข้า", "เข้าบัญชี", "1.00 บาท", "11.67 บาท");
  assert.equal(parseMessage(msg).amount, 1.0);
});

test("flex money-in with thousands separators", () => {
  const msg = kbankFlex("รายการเงินเข้า", "เข้าบัญชี", "12,345.67 บาท", "1,000,000.00 บาท");
  assert.equal(parseMessage(msg).amount, 12345.67);
});

test("flex money-out (รายการโอน/ถอน) is ignored", () => {
  const msg = kbankFlex("รายการโอน/ถอน", "จากบัญชี", "-1.00 บาท", "23,382.88 บาท");
  assert.equal(parseMessage(msg), null);
});

test("flex with only a balance is not a transfer", () => {
  const flex = {
    contentType: "FLEX",
    contentMetadata: { FLEX_JSON: JSON.stringify({
      contents: [{ body: { contents: [
        { type: "text", text: "ยอดเงินคงเหลือ" },
        { type: "text", text: "9,999.00 บาท" },
      ] } }],
    }) },
  };
  assert.equal(parseMessage(flex), null);
});

test("flex with malformed JSON returns null", () => {
  assert.equal(parseMessage({ contentType: "FLEX", contentMetadata: { FLEX_JSON: "{not json" } }), null);
});

test("parseFlexTransfer handles empty input", () => {
  assert.equal(parseFlexTransfer([]), null);
  assert.equal(parseFlexTransfer(null), null);
});
