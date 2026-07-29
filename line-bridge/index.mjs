// PanPay LINE bridge (EXPERIMENTAL).
// Logs into a LINE account via @evex/linejs (a SelfBot library) and, on that one
// account, does two things:
//   1. reads incoming bank "money in" notifications and auto-confirms the
//      matching charge / top-up, and
//   2. replies to a "ยอดเงิน" / "balance" chat message with the wallet balance.
// (Both must share one account — LINE only allows one SelfBot session per login.)
//
// ⚠️ SelfBots violate LINE's Terms of Service and can get the account banned.
// This is a convenience experiment — slip verification remains the source of truth.

import fs from "node:fs";

import { BaseClient } from "@evex/linejs/base";
import { FileStorage } from "@evex/linejs/storage";
import { parseMessage } from "./parser.mjs";

const PANPAY_URL = process.env.PANPAY_URL || "http://localhost:8000";
const API_KEY = process.env.PANPAY_API_KEY; // merchant secret key (sk_live_...)
const INGEST_KEY = process.env.PANPAY_INGEST_KEY; // platform ingest key (optional)
const ACCOUNT = process.env.PANPAY_ACCOUNT; // PromptPay id this bridge's bank account collects into (optional)
// LINE userIds allowed to query the balance (comma-separated). Empty = reply to anyone.
const BALANCE_ALLOWED = (process.env.PANPAY_BALANCE_ALLOWED_IDS || "")
  .split(",").map((s) => s.trim()).filter(Boolean);
const BALANCE_TRIGGERS = ["ยอดเงิน", "ยอด", "balance", "/balance"];

if (!API_KEY) {
  console.error("Set PANPAY_API_KEY (the merchant's sk_live_... key).");
  process.exit(1);
}

const storage = new FileStorage("./storage.json");

// ---- Connection state published to the backend for the admin console ----
let currentStatus = "starting"; // starting | awaiting_qr | awaiting_pin | connected
let lastQrUrl = null;
let lastPin = null;
let displayName = null;
let lineMid = null;
let linePicture = null;

function pictureUrl(me) {
  const p = me?.picturePath || me?.picture;
  return typeof p === "string" && p.startsWith("/") ? `https://profile.line-scdn.net${p}` : null;
}

/** Publish current state to the backend; returns {reconnect} (needs the ingest key). */
async function publishState(status, extra = {}) {
  if (!INGEST_KEY) return { reconnect: false };
  try {
    const res = await fetch(`${PANPAY_URL}/v1/line/bot-state`, {
      method: "POST",
      headers: { "x-ingest-key": INGEST_KEY, "Content-Type": "application/json" },
      body: JSON.stringify({ status, ...extra }),
    });
    return res.ok ? await res.json() : { reconnect: false };
  } catch {
    return { reconnect: false };
  }
}

/** If the admin asked to reconnect, drop the LINE session and restart for a fresh QR. */
async function handleReconnect(resp) {
  if (!resp || !resp.reconnect) return;
  console.log("[LINE] reconnect requested — dropping session, restarting for a fresh QR");
  try { await storage.delete?.(".auth"); } catch { /* ignore */ }
  try { fs.rmSync(new URL("./storage.json", import.meta.url), { force: true }); } catch { /* ignore */ }
  process.exit(0); // systemd restarts us -> no cached token -> QR login
}

function bindHandlers(client) {
  client.on("qrcall", (url) => {
    currentStatus = "awaiting_qr";
    lastQrUrl = url;
    console.log("[LINE] Scan this QR / open to log in:\n", url);
    publishState("awaiting_qr", { qr_url: url });
  });
  client.on("pincall", (pin) => {
    currentStatus = "awaiting_pin";
    lastPin = pin;
    console.log("[LINE] Enter this PIN on your phone:", pin);
    publishState("awaiting_pin", { pin });
  });
  client.on("update:authtoken", (t) => storage.set(".auth", t));
}

/** Return a logged-in client: resume from cache, else QR login (regenerating a
 *  fresh QR whenever the previous one expires, so the admin isn't racing a timer). */
async function connect() {
  const cached = await storage.get(".auth");
  if (typeof cached === "string") {
    const client = new BaseClient({ device: "DESKTOPWIN", storage });
    bindHandlers(client);
    try {
      await client.loginProcess.login({ authToken: cached });
      return client;
    } catch (e) {
      console.log("[LINE] cached token rejected (", e.message, ") — fresh QR login");
      await storage.delete?.(".auth");
    }
  }
  for (let attempt = 1; ; attempt++) {
    const client = new BaseClient({ device: "DESKTOPWIN", storage });
    bindHandlers(client);
    try {
      await client.loginProcess.login({});
      return client;
    } catch (e) {
      console.log(`[LINE] QR login attempt ${attempt} failed (${e.message}) — new QR in 2s`);
      currentStatus = "awaiting_qr";
      await new Promise((r) => setTimeout(r, 2000));
    }
  }
}

async function tryPost(path, headers, payload, label) {
  try {
    const res = await fetch(`${PANPAY_URL}${path}`, {
      method: "POST",
      headers: { ...headers, "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const text = await res.text();
    console.log(`[PanPay] ${label} ${res.status}`, text);
    try { return JSON.parse(text).matched === true; } catch { return false; }
  } catch (e) {
    console.error(`[PanPay] ${label} failed:`, e.message);
    return false;
  }
}

async function reportTransfer(amount, messageId, sender) {
  const ref = `LINE:${messageId}`;
  if (INGEST_KEY) {
    // Shared-account model: one bridge confirms charges for ANY merchant that
    // collects into the watched account, then merchant credit top-ups.
    if (await tryPost("/bank/incoming/platform", { "x-ingest-key": INGEST_KEY },
        { amount, ref, sender_name: sender, account: ACCOUNT }, "charge")) return;
    await tryPost("/topup/incoming", { "x-ingest-key": INGEST_KEY },
        { amount, ref, sender_name: sender }, "topup");
    return;
  }
  // Single-merchant model: match only this API key's charges.
  await tryPost("/v1/line/transfer", { Authorization: `Bearer ${API_KEY}` },
      { amount, message_id: String(messageId), sender }, "charge");
}

function isBalanceQuery(text) {
  if (!text) return false;
  const t = text.trim().toLowerCase();
  return BALANCE_TRIGGERS.some((w) => t === w.toLowerCase() || t.startsWith(w.toLowerCase() + " "));
}

const formatTHB = (n) =>
  new Intl.NumberFormat("th-TH", { style: "currency", currency: "THB" }).format(Number(n) || 0);

async function balanceReply() {
  const res = await fetch(`${PANPAY_URL}/v1/balance`, { headers: { "X-API-Key": API_KEY } });
  if (!res.ok) throw new Error(`/v1/balance ${res.status}`);
  const d = await res.json();
  return `💰 ยอดเงินคงเหลือ: ${formatTHB(d.balance)}\nค่าธรรมเนียม/รายการ: ${formatTHB(d.credit_per_transaction)}`;
}

// Heartbeat: keep the admin console's state fresh and pick up reconnect requests.
setInterval(async () => {
  const extra =
    currentStatus === "awaiting_qr" ? { qr_url: lastQrUrl }
    : currentStatus === "awaiting_pin" ? { pin: lastPin }
    : currentStatus === "connected" ? { display_name: displayName, mid: lineMid, picture_url: linePicture }
    : {};
  handleReconnect(await publishState(currentStatus, extra));
}, 5000);

const client = await connect();
currentStatus = "connected";
try {
  const me = await client.talk.getProfile();
  displayName = me.displayName;
  lineMid = me.mid;
  linePicture = pictureUrl(me);
} catch { /* profile is best-effort */ }
await publishState("connected", { display_name: displayName, mid: lineMid, picture_url: linePicture });
console.log(`[LINE] Logged in${displayName ? ` as ${displayName}` : ""}. Listening…`);

for await (const op of client.createPolling().listenTalkEvents()) {
  if (op.type !== "RECEIVE_MESSAGE") continue;
  let msg;
  try {
    msg = await client.e2ee.decryptE2EEMessage(op.message);
  } catch {
    msg = op.message;
  }

  // 1) Balance query ("ยอดเงิน" / "balance") — reply with the wallet balance.
  const text = msg?.text ?? op.message?.text;
  if (isBalanceQuery(text)) {
    const senderId = op.message?._from ?? msg?.from;
    if (BALANCE_ALLOWED.length && !BALANCE_ALLOWED.includes(senderId)) {
      console.log("[LINE] ignoring balance query from non-allowlisted id:", senderId);
      continue;
    }
    let reply;
    try {
      reply = await balanceReply();
    } catch (e) {
      console.error("[PanPay] balance fetch failed:", e.message);
      reply = "ขออภัย ดึงยอดเงินไม่สำเร็จ กรุณาลองใหม่ภายหลัง";
    }
    try {
      await client.talk.sendMessage({ to: msg.from, text: reply, e2ee: !!op.message.chunks });
      console.log("[LINE] replied balance to", senderId);
    } catch (e) {
      console.error("[LINE] reply failed:", e.message);
    }
    continue;
  }

  // 2) Bank "money in" notification — auto-confirm the matching charge / top-up.
  const parsed = parseMessage(msg);
  if (!parsed) continue;
  const messageId = op.message?.id ?? `${Date.now()}`;
  console.log(`[LINE] Transfer detected: ${parsed.amount} (msg ${messageId})`);
  await reportTransfer(parsed.amount, messageId, msg?.from);
}
