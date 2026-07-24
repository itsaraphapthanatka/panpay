// Parse a Thai bank "money in" LINE notification into a transfer amount.
// Pure + dependency-free so it can be unit-tested without linejs / a LINE login.

// Keywords that indicate an INCOMING transfer (ignore withdrawals / balances).
const CREDIT_KEYWORDS = [
  /เงินเข้า/,
  /เงินโอนเข้า/,
  /รับโอน/,
  /รับเงิน/,
  /โอนเข้า/,
  /เข้าบัญชี/,
  /received/i,
  /credited?/i,
];

export function parseTransfer(text) {
  if (!text || typeof text !== "string") return null;
  if (!CREDIT_KEYWORDS.some((re) => re.test(text))) return null;

  // "1,234.56 บาท" / "500.00 THB" / "฿250.00"
  const m =
    text.match(/([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{1,2})?|[0-9]+(?:\.[0-9]{1,2})?)\s*(?:บาท|THB|baht)/i) ||
    text.match(/(?:฿|THB)\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)/i);
  if (!m) return null;

  const amount = parseFloat(m[1].replace(/,/g, ""));
  if (!Number.isFinite(amount) || amount <= 0) return null;
  return { amount, text };
}
