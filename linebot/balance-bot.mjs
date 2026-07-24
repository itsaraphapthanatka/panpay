/**
 * LINE SelfBot — balance check (@evex/linejs)
 * ===========================================
 *
 * Listens for a "ยอดเงิน" / "balance" chat message and replies with the
 * merchant's wallet balance, fetched from the panpay backend.
 *
 * ⚠️  This is a LINE *SelfBot*: it logs in as a real LINE user account, which
 *     is against LINE's Terms of Service and can get the account banned. Use a
 *     throwaway account and only where you accept that risk. For production,
 *     prefer the official LINE Messaging API (already wired at
 *     backend/app/routers/line.py).
 *
 * Setup:
 *   cd linebot
 *   npm install            # installs @evex/linejs (see package.json)
 *   cp .env.example .env    # fill in the values below
 *   node balance-bot.mjs    # first run prints a QR / PIN to log in
 *
 * Env vars (see .env.example):
 *   PANPAY_API_BASE      e.g. https://punpay.petgo.asia   (no trailing slash)
 *   PANPAY_API_KEY       merchant secret key, starts with sk_
 *   ALLOWED_LINE_IDS     optional comma-separated LINE userIds allowed to ask;
 *                        empty = reply to anyone (not recommended)
 */

import { BaseClient } from "@evex/linejs/base";
import { FileStorage } from "@evex/linejs/storage";
import qrcode from "qrcode-terminal";

// Load .env when present so a plain `node balance-bot.mjs` works (not just
// `npm start`, which passes --env-file). No-op if the file is missing.
try {
  process.loadEnvFile(new URL("./.env", import.meta.url));
} catch {
  /* no .env file — rely on the process environment */
}

const API_BASE = (process.env.PANPAY_API_BASE || "").replace(/\/+$/, "");
const API_KEY = process.env.PANPAY_API_KEY || "";
const ALLOWED = (process.env.ALLOWED_LINE_IDS || "")
  .split(",")
  .map((s) => s.trim())
  .filter(Boolean);

if (!API_BASE || !API_KEY) {
  console.error("Missing PANPAY_API_BASE or PANPAY_API_KEY — see .env.example");
  process.exit(1);
}

// Trigger words (case-insensitive). Thai + English.
const TRIGGERS = ["ยอดเงิน", "ยอด", "balance", "/balance"];

function isBalanceQuery(text) {
  if (!text) return false;
  const t = text.trim().toLowerCase();
  return TRIGGERS.some((w) => t === w.toLowerCase() || t.startsWith(w.toLowerCase() + " "));
}

/** Fetch the merchant balance from panpay via the non-expiring API key. */
async function fetchBalance() {
  const res = await fetch(`${API_BASE}/v1/balance`, {
    headers: { "X-API-Key": API_KEY },
  });
  if (!res.ok) {
    throw new Error(`panpay /v1/balance ${res.status}: ${await res.text()}`);
  }
  return res.json(); // { balance, credit_per_transaction, entries: [...] }
}

function formatTHB(n) {
  return new Intl.NumberFormat("th-TH", {
    style: "currency",
    currency: "THB",
  }).format(Number(n) || 0);
}

async function main() {
  const storage = new FileStorage("./storage.json");
  const client = new BaseClient({ device: "DESKTOPWIN", storage });

  client.on("qrcall", (url) => {
    console.log("\nScan this QR with the LINE mobile app (do NOT open it in a browser):\n");
    qrcode.generate(url, { small: true });
    console.log("\n(raw url, if your app needs it):", url, "\n");
  });
  client.on("pincall", (pin) => console.log("\n>>> Enter this PIN number in your LINE app:", pin, "\n"));
  client.on("update:authtoken", (t) => storage.set(".auth", t));

  const cached = await storage.get(".auth");
  try {
    await client.loginProcess.login(
      typeof cached === "string" ? { authToken: cached } : {},
    );
  } catch (e) {
    // Stale/revoked token (e.g. V3_TOKEN_CLIENT_LOGGED_OUT) — drop it and
    // fall back to a fresh QR login.
    if (typeof cached === "string") {
      console.log("Cached token rejected (", e.message, ") — starting fresh QR login…");
      await storage.delete?.(".auth");
      await client.loginProcess.login({});
    } else {
      throw e;
    }
  }
  try {
    const me = await client.talk.getProfile();
    console.log(`Logged in as: ${me.displayName}  (userId/mid: ${me.mid})`);
    console.log("  ↳ This is the BOT account. Message it FROM ANOTHER LINE account to test.");
  } catch (e) {
    console.log("Logged in (could not fetch own profile:", e.message, ")");
  }
  console.log("Listening for balance queries…");

  for await (const op of client.createPolling().listenTalkEvents()) {
    if (op.type !== "RECEIVE_MESSAGE") continue;

    let msg;
    try {
      msg = await client.e2ee.decryptE2EEMessage(op.message);
    } catch {
      msg = op.message; // non-e2ee message
    }

    const text = msg?.text ?? op.message?.text;
    if (!isBalanceQuery(text)) continue;

    const senderId = op.message?._from ?? msg?.from;
    if (ALLOWED.length && !ALLOWED.includes(senderId)) {
      console.log("Ignoring balance query from non-allowlisted id:", senderId);
      continue;
    }

    let reply;
    try {
      const data = await fetchBalance();
      reply = `💰 ยอดเงินคงเหลือ: ${formatTHB(data.balance)}\n` +
        `ค่าธรรมเนียม/รายการ: ${formatTHB(data.credit_per_transaction)}`;
    } catch (err) {
      console.error("balance fetch failed:", err);
      reply = "ขออภัย ดึงยอดเงินไม่สำเร็จ กรุณาลองใหม่ภายหลัง";
    }

    await client.talk.sendMessage({
      to: msg.from,
      text: reply,
      e2ee: !!op.message.chunks,
    });
  }
}

main().catch((err) => {
  console.error("fatal:", err);
  process.exit(1);
});
