// Per-merchant LINE bot worker (one child process per merchant, spawned by
// manager.mjs). Logs into THIS merchant's LINE account and, on that account:
//   1. auto-confirms the merchant's charges from bank "money in" alerts, and
//   2. replies to "ยอดเงิน" / "balance" with the merchant's wallet balance.
// All backend calls use the platform ingest key + merchant_id — the worker never
// holds a merchant API key.
//
// ⚠️ SelfBot: violates LINE's ToS, account can be banned. Use throwaway accounts.

import fs from "node:fs";

import { BaseClient } from "@evex/linejs/base";
import { FileStorage } from "@evex/linejs/storage";
import { parseMessage } from "./parser.mjs";

const PANPAY_URL = process.env.PANPAY_URL || "http://localhost:8000";
const INGEST_KEY = process.env.PANPAY_INGEST_KEY;
const MERCHANT_ID = process.env.MERCHANT_ID;
const STORAGE_FILE = process.env.STORAGE_FILE || `./storage-${MERCHANT_ID}.json`;
const BALANCE_TRIGGERS = ["ยอดเงิน", "ยอด", "balance", "/balance"];

if (!INGEST_KEY || !MERCHANT_ID) {
  console.error("[worker] need PANPAY_INGEST_KEY and MERCHANT_ID");
  process.exit(1);
}

const tag = `[worker ${MERCHANT_ID}]`;
const storage = new FileStorage(STORAGE_FILE);

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

const ingestHeaders = { "x-ingest-key": INGEST_KEY, "Content-Type": "application/json" };

/** Publish this merchant's bot state; returns {enabled, action}. */
async function publishState(status, extra = {}) {
  try {
    const res = await fetch(`${PANPAY_URL}/v1/line/manager/state`, {
      method: "POST",
      headers: ingestHeaders,
      body: JSON.stringify({ merchant_id: MERCHANT_ID, status, ...extra }),
    });
    return res.ok ? await res.json() : { enabled: true, action: "" };
  } catch {
    return { enabled: true, action: "" };
  }
}

/** Act on a one-shot reconnect: drop the LINE session and exit (manager re-forks). */
function maybeReconnect(resp) {
  if (resp && resp.action === "reconnect") {
    console.log(`${tag} reconnect requested — dropping session, exiting for a fresh QR`);
    try { fs.rmSync(new URL(STORAGE_FILE, import.meta.url), { force: true }); } catch { /* ignore */ }
    process.exit(0);
  }
}

async function reportTransfer(amount, messageId, sender) {
  try {
    const res = await fetch(`${PANPAY_URL}/bank/incoming/for-merchant`, {
      method: "POST",
      headers: ingestHeaders,
      body: JSON.stringify({ merchant_id: MERCHANT_ID, amount, ref: `LINE:${messageId}`, sender_name: sender }),
    });
    console.log(`${tag} charge ${res.status}`, await res.text());
  } catch (e) {
    console.error(`${tag} report failed:`, e.message);
  }
}

const formatTHB = (n) =>
  new Intl.NumberFormat("th-TH", { style: "currency", currency: "THB" }).format(Number(n) || 0);

async function balanceReply() {
  const res = await fetch(`${PANPAY_URL}/v1/line/manager/balance/${MERCHANT_ID}`, {
    headers: { "x-ingest-key": INGEST_KEY },
  });
  if (!res.ok) throw new Error(`balance ${res.status}`);
  const d = await res.json();
  return `💰 ยอดเงินคงเหลือ: ${formatTHB(d.balance)}\nค่าธรรมเนียม/รายการ: ${formatTHB(d.credit_per_transaction)}`;
}

function isBalanceQuery(text) {
  if (!text) return false;
  const t = text.trim().toLowerCase();
  return BALANCE_TRIGGERS.some((w) => t === w.toLowerCase() || t.startsWith(w.toLowerCase() + " "));
}

function bindHandlers(client) {
  client.on("qrcall", (url) => {
    currentStatus = "awaiting_qr";
    lastQrUrl = url;
    console.log(`${tag} QR:`, url);
    publishState("awaiting_qr", { qr_url: url });
  });
  client.on("pincall", (pin) => {
    currentStatus = "awaiting_pin";
    lastPin = pin;
    console.log(`${tag} PIN:`, pin);
    publishState("awaiting_pin", { pin });
  });
  client.on("update:authtoken", (t) => storage.set(".auth", t));
}

async function connect() {
  const cached = await storage.get(".auth");
  if (typeof cached === "string") {
    const client = new BaseClient({ device: "DESKTOPWIN", storage });
    bindHandlers(client);
    try { await client.loginProcess.login({ authToken: cached }); return client; }
    catch (e) { console.log(`${tag} cached token rejected (${e.message}) — fresh QR`); await storage.delete?.(".auth"); }
  }
  for (let attempt = 1; ; attempt++) {
    const client = new BaseClient({ device: "DESKTOPWIN", storage });
    bindHandlers(client);
    try { await client.loginProcess.login({}); return client; }
    catch (e) {
      console.log(`${tag} QR login attempt ${attempt} failed (${e.message}) — new QR in 2s`);
      currentStatus = "awaiting_qr";
      await new Promise((r) => setTimeout(r, 2000));
    }
  }
}

// Heartbeat: keep state fresh and pick up reconnect requests.
setInterval(async () => {
  const extra =
    currentStatus === "awaiting_qr" ? { qr_url: lastQrUrl }
    : currentStatus === "awaiting_pin" ? { pin: lastPin }
    : currentStatus === "connected" ? { display_name: displayName, mid: lineMid, picture_url: linePicture }
    : {};
  maybeReconnect(await publishState(currentStatus, extra));
}, 5000);

const client = await connect();
currentStatus = "connected";
try {
  const me = await client.talk.getProfile();
  displayName = me.displayName;
  lineMid = me.mid;
  linePicture = pictureUrl(me);
} catch { /* best effort */ }
await publishState("connected", { display_name: displayName, mid: lineMid, picture_url: linePicture });
console.log(`${tag} logged in${displayName ? ` as ${displayName}` : ""}. Listening…`);

for await (const op of client.createPolling().listenTalkEvents()) {
  if (op.type !== "RECEIVE_MESSAGE") continue;
  let msg;
  try { msg = await client.e2ee.decryptE2EEMessage(op.message); } catch { msg = op.message; }

  const text = msg?.text ?? op.message?.text;
  if (isBalanceQuery(text)) {
    let reply;
    try { reply = await balanceReply(); }
    catch (e) { console.error(`${tag} balance failed:`, e.message); reply = "ขออภัย ดึงยอดเงินไม่สำเร็จ ลองใหม่ภายหลัง"; }
    try { await client.talk.sendMessage({ to: msg.from, text: reply, e2ee: !!op.message.chunks }); }
    catch (e) { console.error(`${tag} reply failed:`, e.message); }
    continue;
  }

  const parsed = parseMessage(msg);
  if (!parsed) continue;
  const messageId = op.message?.id ?? `${Date.now()}`;
  console.log(`${tag} transfer detected: ${parsed.amount} (msg ${messageId})`);
  await reportTransfer(parsed.amount, messageId, msg?.from);
}
