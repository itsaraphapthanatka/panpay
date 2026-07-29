// Parse a Thai bank "money in" LINE notification into a transfer amount.
// Pure + dependency-free so it can be unit-tested without linejs / a LINE login.
//
// Banks deliver alerts two ways:
//   1. Plain text ("เงินเข้า 1,234.56 บาท")  -> parseTransfer(text)
//   2. Flex/card messages (KBank Live etc.) -> parseFlexTransfer(flexTexts)
// Use parseMessage(msg) to handle either automatically.

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

// Keywords that mark an OUTGOING transfer / withdrawal — reject these outright,
// even if some credit keyword also appears in the card boilerplate.
const DEBIT_KEYWORDS = [
  /รายการโอน\s*\/\s*ถอน/,
  /โอนออก/,
  /เงินออก/,
  /ถอนเงิน/,
  /ถอนออก/,
  /withdraw/i,
  /debited?/i,
];

// A baht amount token, e.g. "1,234.56", "500.00", "1.00".
const AMOUNT_RE = /([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{1,2})?|[0-9]+(?:\.[0-9]{1,2})?)/;

function toAmount(str) {
  if (!str) return null;
  const m = str.match(AMOUNT_RE);
  if (!m) return null;
  const amount = parseFloat(m[1].replace(/,/g, ""));
  return Number.isFinite(amount) && amount > 0 ? amount : null;
}

/** Recursively collect the `text` of every text node in a flex bubble, in order. */
export function extractFlexTexts(flexJson) {
  const out = [];
  const walk = (node) => {
    if (Array.isArray(node)) {
      node.forEach(walk);
      return;
    }
    if (node && typeof node === "object") {
      if (node.type === "text" && typeof node.text === "string") out.push(node.text);
      if (Array.isArray(node.contents)) node.contents.forEach(walk);
      // A flex payload is { contents: [ {body|bubble...}, ... ] }; recurse into
      // wrapper keys we haven't handled above so nested bubbles are covered.
      for (const k of ["body", "hero", "footer", "header", "bubble"]) {
        if (node[k]) walk(node[k]);
      }
      if (node.type === "carousel" || node.type === "bubble") {
        for (const v of Object.values(node)) {
          if (v && typeof v === "object") walk(v);
        }
      }
    }
  };
  walk(flexJson);
  return out;
}

/**
 * Parse an ordered list of flex text nodes into a transfer amount.
 * Prefers the amount paired with "จำนวนเงิน" and never returns the balance
 * ("ยอดเงินคงเหลือ"). Returns { amount, text } or null.
 */
export function parseFlexTransfer(texts) {
  if (!Array.isArray(texts) || !texts.length) return null;
  const blob = texts.join("\n");
  if (DEBIT_KEYWORDS.some((re) => re.test(blob))) return null;
  if (!CREDIT_KEYWORDS.some((re) => re.test(blob))) return null;

  const isBalanceLabel = (t) => /คงเหลือ/.test(t);

  // 1) Prefer the value that follows the "จำนวนเงิน" (amount) label.
  const amountIdx = texts.findIndex((t) => /จำนวนเงิน/.test(t));
  if (amountIdx >= 0) {
    for (let i = amountIdx + 1; i < texts.length; i++) {
      if (isBalanceLabel(texts[i])) continue;
      const amt = toAmount(texts[i]);
      if (amt !== null) return { amount: amt, text: blob };
    }
  }

  // 2) Fallback: the first baht amount that isn't the balance.
  for (let i = 0; i < texts.length; i++) {
    if (isBalanceLabel(texts[i])) continue;
    // Skip the value node right after a balance label.
    if (i > 0 && isBalanceLabel(texts[i - 1])) continue;
    if (!/บาท|฿|THB/i.test(texts[i])) continue;
    const amt = toAmount(texts[i]);
    if (amt !== null) return { amount: amt, text: blob };
  }
  return null;
}

export function parseTransfer(text) {
  if (!text || typeof text !== "string") return null;
  if (!CREDIT_KEYWORDS.some((re) => re.test(text))) return null;
  if (DEBIT_KEYWORDS.some((re) => re.test(text))) return null;

  // Amounts like "1,234.56 บาท" / "1.01 บ" (BAAC abbreviates บาท -> บ) / "500 THB".
  // Skip the balance — the amount after "คงเหลือ" — so we return the transfer amount.
  // "บ" only counts as the baht unit when not followed by another Thai letter
  // (so "บช" = บัญชี, "บาท" handled separately, aren't mistaken for it).
  const re = /([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{1,2})?|[0-9]+(?:\.[0-9]{1,2})?)\s*(?:บาท|บ(?=\s|$|[^ก-๙])|THB|baht)/gi;
  let m;
  while ((m = re.exec(text)) !== null) {
    const before = text.slice(Math.max(0, m.index - 12), m.index);
    if (/คงเหลือ/.test(before)) continue; // this is the balance, not the transfer
    const amount = parseFloat(m[1].replace(/,/g, ""));
    if (Number.isFinite(amount) && amount > 0) return { amount, text };
  }
  // Fallback: "฿250.00" prefix form.
  const p = text.match(/(?:฿|THB)\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)/i);
  if (p) {
    const amount = parseFloat(p[1].replace(/,/g, ""));
    if (Number.isFinite(amount) && amount > 0) return { amount, text };
  }
  return null;
}

/**
 * Handle either a plain-text or a flex bank notification.
 * `msg` is a linejs message object. Returns { amount, text } or null.
 */
export function parseMessage(msg) {
  if (!msg) return null;
  if (msg.contentType === "FLEX" || msg.contentType === "TEMPLATE") {
    const raw = msg.contentMetadata?.FLEX_JSON;
    if (!raw) return null;
    let flex;
    try {
      flex = JSON.parse(raw);
    } catch {
      return null;
    }
    return parseFlexTransfer(extractFlexTexts(flex));
  }
  return parseTransfer(msg.text);
}
