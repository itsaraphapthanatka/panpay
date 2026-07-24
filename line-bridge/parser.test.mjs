import { test } from "node:test";
import assert from "node:assert/strict";
import { parseTransfer } from "./parser.mjs";

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
