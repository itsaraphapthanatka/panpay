// PanPay LINE bridge (EXPERIMENTAL).
// Logs into a LINE account via @evex/linejs (a SelfBot library), reads incoming
// bank "money in" notifications, parses the amount, and reports it to PanPay,
// which matches it to a single pending charge of that amount.
//
// ⚠️ SelfBots violate LINE's Terms of Service and can get the account banned.
// This is a convenience experiment — slip verification remains the source of truth.

import { BaseClient } from "@evex/linejs/base";
import { FileStorage } from "@evex/linejs/storage";
import { parseMessage } from "./parser.mjs";

const PANPAY_URL = process.env.PANPAY_URL || "http://localhost:8000";
const API_KEY = process.env.PANPAY_API_KEY; // merchant secret key (sk_live_...)

if (!API_KEY) {
  console.error("Set PANPAY_API_KEY (the merchant's sk_live_... key).");
  process.exit(1);
}

const storage = new FileStorage("./storage.json");
const client = new BaseClient({ device: "DESKTOPWIN", storage });

client.on("qrcall", (url) => console.log("[LINE] Scan this QR / open to log in:\n", url));
client.on("pincall", (pin) => console.log("[LINE] Enter this PIN on your phone:", pin));
client.on("update:authtoken", (t) => storage.set(".auth", t));

async function reportTransfer(amount, messageId, text, sender) {
  try {
    const res = await fetch(`${PANPAY_URL}/v1/line/transfer`, {
      method: "POST",
      headers: { Authorization: `Bearer ${API_KEY}`, "Content-Type": "application/json" },
      body: JSON.stringify({ amount, message_id: String(messageId), text, sender }),
    });
    console.log(`[PanPay] ${res.status}`, await res.text());
  } catch (e) {
    console.error("[PanPay] report failed:", e.message);
  }
}

const cached = await storage.get(".auth");
await client.loginProcess.login(typeof cached === "string" ? { authToken: cached } : {});
console.log("[LINE] Logged in. Listening for transfer notifications…");

for await (const op of client.createPolling().listenTalkEvents()) {
  if (op.type !== "RECEIVE_MESSAGE") continue;
  let msg;
  try {
    msg = await client.e2ee.decryptE2EEMessage(op.message);
  } catch {
    msg = op.message;
  }
  const parsed = parseMessage(msg);
  if (!parsed) continue;
  const messageId = op.message?.id ?? `${Date.now()}`;
  console.log(`[LINE] Transfer detected: ${parsed.amount} (msg ${messageId})`);
  await reportTransfer(parsed.amount, messageId, parsed.text, msg?.from);
}
