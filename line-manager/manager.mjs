// PanPay LINE multi-tenant manager.
// Polls the backend for merchants that want a LINE bot and reconciles one child
// worker process per merchant (fork/kill). Each worker logs into that merchant's
// LINE account and handles their auto-confirm + balance queries.
//
// One managed service instead of a systemd unit per merchant — workers are
// spawned/killed automatically as merchants connect/disconnect from their
// dashboard. Auth to the backend is the platform ingest key only.

import { fork } from "node:child_process";
import { fileURLToPath } from "node:url";

const PANPAY_URL = process.env.PANPAY_URL || "http://localhost:8000";
const INGEST_KEY = process.env.PANPAY_INGEST_KEY;
const POLL_MS = Number(process.env.MANAGER_POLL_MS || 5000);

if (!INGEST_KEY) {
  console.error("[manager] set PANPAY_INGEST_KEY");
  process.exit(1);
}

const WORKER = fileURLToPath(new URL("./worker.mjs", import.meta.url));
const children = new Map(); // merchant_id -> ChildProcess

async function fetchEnabled() {
  try {
    const res = await fetch(`${PANPAY_URL}/v1/line/manager/merchants`, {
      headers: { "x-ingest-key": INGEST_KEY },
    });
    if (!res.ok) {
      console.error("[manager] merchants list HTTP", res.status);
      return null;
    }
    const d = await res.json();
    return Array.isArray(d.merchant_ids) ? d.merchant_ids : [];
  } catch (e) {
    console.error("[manager] backend unreachable:", e.message);
    return null;
  }
}

function startWorker(mid) {
  console.log("[manager] start worker", mid);
  const child = fork(WORKER, [], { env: { ...process.env, MERCHANT_ID: mid } });
  children.set(mid, child);
  child.on("exit", (code) => {
    console.log(`[manager] worker ${mid} exited (code ${code})`);
    if (children.get(mid) === child) children.delete(mid);
    // The reconcile loop re-forks if the merchant is still enabled
    // (covers a reconnect request and crashes alike).
  });
}

function stopWorker(mid) {
  const child = children.get(mid);
  if (!child) return;
  console.log("[manager] stop worker", mid);
  children.delete(mid);
  child.kill();
}

async function reconcile() {
  const enabled = await fetchEnabled();
  if (enabled === null) return; // backend down — keep current workers as-is
  const want = new Set(enabled);
  for (const mid of want) if (!children.has(mid)) startWorker(mid);
  for (const mid of [...children.keys()]) if (!want.has(mid)) stopWorker(mid);
}

console.log("[manager] PanPay LINE multi-tenant manager starting…");
await reconcile();
setInterval(reconcile, POLL_MS);
