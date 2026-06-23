# PanPay — PromptPay Payment Gateway

A self-hosted payment gateway in the style of [paynoi.com](https://paynoi.com): merchants
generate dynamic **PromptPay QR codes**, customers pay directly into the merchant's bank
account, and the system confirms payment via **slip verification** — then fires a webhook.
No money is ever held on PanPay's side; it only *verifies* that a transfer happened.

- **Backend:** FastAPI + SQLAlchemy + PostgreSQL
- **Frontend:** React + Vite
- **Payment detection:** Slip Verification API (pluggable — SlipOK for production, a `dev`
  provider for local end-to-end testing without a bank)

> ⚠️ **Legal note (Thailand):** Operating a real payment service is regulated by the Bank of
> Thailand. The slip-verification model keeps you on safer ground because funds go straight to
> the merchant's account and PanPay only confirms the transfer — but verify your obligations
> before going live commercially.

---

## Architecture

```
Merchant system ──(API key)──▶  POST /v1/charges ──▶ creates Charge + PromptPay QR
                                                         │
Customer ──opens──▶ /pay/{charge_id}  ◀── checkout page (QR + amount)
   │ pays via bank app, then uploads the slip image
   ▼
POST /checkout/{id}/slip ──▶ read QR from slip (OpenCV) ──▶ Slip Verify API
                                                       ──▶ match amount + mark Charge paid
                                                         │
                                                         ▼
                          POST merchant.webhook_url  (X-Panpay-Signature: HMAC-SHA256)
```

**Automatic slip QR reading:** when the customer uploads a slip image, the QR embedded in it
is decoded locally with OpenCV ([`app/slip_qr.py`](backend/app/slip_qr.py)) — no manual
reference entry. The decoded payload uniquely identifies the transfer and becomes the
`trans_ref`, so the same slip can never be reused (a re-upload returns `409`).

Key safeguards: each bank `trans_ref` is globally unique (a slip can't be reused), submitted
slip amount must equal the charge amount, and webhooks are HMAC-signed.

---

## Run the whole stack with Docker

The fastest way to run everything (Postgres + backend + frontend):

```bash
docker compose up --build       # db + backend (:8000) + frontend (:5173)
docker compose exec backend python seed.py   # optional: demo merchant + API key
```

Then open http://localhost:5173 (login `demo@panpay.io` / `demo1234`). The backend
runs `alembic upgrade head` on startup, so the schema is created automatically.
The compose Postgres is published on host port **5433** (so it won't clash with a local
Postgres on 5432); the backend reaches it internally as `db:5432`. Stop with `docker compose down`.

CI (`.github/workflows/ci.yml`) runs the pytest suite against a Postgres service,
builds the frontend, and builds both Docker images on every push/PR.

---

## Quick start (local dev, no Docker)

### 1. Database (pick one)

**Option A — Docker (Postgres only):** publishes on host :5433, so set
`DATABASE_URL=postgresql+psycopg://panpay:panpay@localhost:5433/panpay` in `backend/.env`.
```bash
docker compose up -d db     # starts Postgres on localhost:5433
```

**Option B — local Postgres (Homebrew):**
```bash
brew services start postgresql@16
psql -d postgres -c "CREATE ROLE panpay LOGIN PASSWORD 'panpay';"
psql -d postgres -c "CREATE DATABASE panpay OWNER panpay;"
```

### 2. Backend
```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # defaults already target the local Postgres above
alembic upgrade head          # create/upgrade the schema (Alembic-managed)
python seed.py                # creates a demo merchant + prints an API key (also runs migrations)
python create_admin.py admin@panpay.io changeme   # create a platform admin (also runs migrations)
uvicorn app.main:app --reload --port 8000
```
API docs: http://localhost:8000/docs

### 3. Frontend
```bash
cd frontend
npm install
cp .env.example .env
npm run dev                   # http://localhost:5173
```

### Or run both at once
```bash
./dev.sh
```

**Demo login:** `demo@panpay.io` / `demo1234`

**Admin console:** http://localhost:5173/admin/login — the platform operator view across
every merchant (oversee merchants, adjust fees, suspend accounts, browse all
transactions/settlements, and the platform-wide audit log). Create an admin with
`python create_admin.py <email> <password>`, or set `ADMIN_BOOTSTRAP_EMAIL` /
`ADMIN_BOOTSTRAP_PASSWORD` in the backend env to auto-create the first admin on startup.

---

## Trying the full flow

1. Log into the dashboard → **ภาพรวม** → "สร้างลิงก์รับชำระเงิน" → enter an amount.
2. Open the generated **checkout link** (`/pay/{id}`) — you'll see the PromptPay QR.
3. Click **ยืนยันการชำระเงิน** (in `dev` mode this simulates a verified slip).
4. The charge flips to **paid**, the dashboard updates, and a webhook is sent (if configured).

### Create a charge from your own backend (API key auth)
```bash
curl -X POST http://localhost:8000/v1/charges \
  -H "Authorization: Bearer sk_live_xxx" \
  -H "Content-Type: application/json" \
  -d '{"amount": 100.00, "reference": "order-123", "description": "Coffee", "account_id": "rcv_..."}'

# Void a pending charge (cancel before payment)
curl -X POST http://localhost:8000/v1/charges/chg_xxx/void -H "Authorization: Bearer sk_live_xxx"

# Refund a paid charge (records the refund + fires charge.refunded)
curl -X POST http://localhost:8000/v1/charges/chg_xxx/refund \
  -H "Authorization: Bearer sk_live_xxx" -H "Content-Type: application/json" \
  -d '{"reason": "customer request"}'
```
> **Refund semantics:** because funds settle directly into the merchant's bank account
> (PanPay never holds money), a refund **records** the reversal and notifies your system —
> the merchant performs the actual transfer back to the customer.

### Embed a popup checkout in your own site
Drop in one script — the checkout opens in a modal (no redirect), like Stripe/paynoi.
The backend serves `panpay.js` at `/panpay.js`.

```html
<script src="http://localhost:8000/panpay.js"></script>
<script>
  // chargeId comes from POST /v1/charges on your server
  PanPay.checkout({
    chargeId: "chg_xxxxxxxxxxxx",
    onSuccess: function (e) { console.log("paid", e.amount); },
    onClose:   function () { /* user closed the modal */ },
  });
</script>
```
The modal loads `/pay/{id}?embed=1` in an iframe and reports completion to the parent via
`postMessage` (`panpay:paid` / `panpay:close`). A live demo page is at
http://localhost:5173/embed-demo.html. The dashboard also has a **"จ่ายแบบ popup"** button
to try it after creating a charge.

---

## Going to production

| Concern | What to do |
|---|---|
| **Real slip verification** | Set `SLIP_PROVIDER` to `slipok` (`SLIPOK_API_KEY` + `SLIPOK_BRANCH_ID`) or `easyslip` (`EASYSLIP_API_KEY`) in `backend/.env`. Adapters live in `app/slip_verify.py` — add more by subclassing `SlipVerifier`. Real providers return the payer name, sending bank, and transfer time, which are stored on the `Payment` row, shown in the dashboard (expand a paid row) and on the success page, and included in the webhook payload. |
| **Secrets** | Change `JWT_SECRET` to a long random value. |
| **Receiving accounts** | A merchant can hold several PromptPay destinations (per branch/product) under **Settings → บัญชีรับเงิน**; one is the default. A charge picks one via `account_id`, else the default, else the merchant's main PromptPay ID. |
| **Webhooks** | Merchant sets `webhook_url` in Settings; verify the `X-Panpay-Signature` HMAC using their `webhook_secret`. Events: `charge.paid`, `charge.refunded`, `charge.canceled`. |
| **Reports & receipts** | Export transactions as CSV (UTF-8 BOM for Excel) from **รายการชำระเงิน → Export CSV** or `GET /dashboard/charges/export.csv`. Each paid/refunded charge has a PDF receipt at `GET /checkout/{id}/receipt.pdf` (`app/pdf_receipt.py`); Thai renders via a runtime-resolved TTF — drop an OFL font in `app/assets/fonts/` for portable production (see that folder's README). |
| **Membership / subscriptions** | Merchants create recurring **plans** (day/month/year interval); customers subscribe as **members** and pay each cycle via PromptPay. Since PromptPay can't auto-charge, each cycle issues an invoice (a Charge) — paying it activates/extends the membership (`app/subscription_ops.py`, statuses `pending`→`active`→`past_due`→`expired`). Manage under the **สมาชิก** page. |
| **Renewal job (cron)** | `app/jobs.py:run_due_renewals` expires lapsed members (past period end + `SUBSCRIPTION_GRACE_DAYS`) and issues renewal invoices for all merchants. Run it on a schedule: `python -m app.jobs` (system cron / k8s CronJob), or set `RUN_SCHEDULER=true` to run it inside the API process every `SCHEDULER_INTERVAL_HOURS` (single instance only). |
| **Subscription webhooks** | Fires `subscription.activated` / `subscription.renewed` (on member payment), `subscription.canceled`, and `subscription.expired` (from the renewal job) to the merchant's `webhook_url`, HMAC-signed like charge events. |
| **Member portal** | Each subscription has an unguessable `portal_token`; the member opens `/m/{token}` (public, no login) to see status + history and pay/renew via PromptPay (`app/routers/portal.py`). The portal link is shown per member in the dashboard. |
| **Coupons / discounts** | Merchants create percent or fixed-amount coupons (`once` = first invoice, or `forever` = every invoice) with optional expiry/redemption caps. Apply by passing `coupon_code` when subscribing — the invoice amount is discounted (`app/subscription_ops.py:apply_coupon`). Manage on the **สมาชิก** page. |
| **Plan change (proration)** | `POST /dashboard/subscriptions/{id}/change-plan` switches a member's plan; for an active member it issues a prorated invoice for the remaining period's price difference (upgrades charge the difference, downgrades take effect next cycle). Proration invoices don't extend the period. |
| **Member notifications** | Bill (`invoice.issued`) and payment (`payment.received`) notifications to the member via **email** (SMTP — e.g. Brevo free tier: `smtp-relay.brevo.com`), **SMS** (generic HTTP gateway), and **LINE** (Messaging API push — free within quota; set `LINE_CHANNEL_ACCESS_TOKEN`, store the member's LINE userId). Channels with no config are recorded to `NotificationLog` as `skipped`; view via `GET /dashboard/notifications` or the **สมาชิก** page. See `app/notifications.py`. |
| **MRR / churn analytics** | `GET /dashboard/subscription-stats` returns MRR (plan prices normalized to monthly), ARR, active members, new-this-month, and churn rate (uses `Subscription.ended_at`). Shown as cards on the **สมาชิก** page. |
| **Settlement / payout** | Batch unsettled paid charges into a settlement with fee (merchant `fee_percent`/`fee_fixed`) → gross/fee/net, then mark it paid out. See the **Settlement** page or `/dashboard/settlements*`. Because funds settle directly to the merchant, this is for **reconciliation/fees/reporting**, not holding balances. |
| **Rate limiting** | In-memory fixed-window limits guard `/auth/*` (per IP), `/checkout/*/slip` (per IP), and `/v1/*` (per API key) — see `app/ratelimit.py`. For multi-instance deploys, back it with Redis. |
| **Audit log** | Security/finance actions (login, key create/revoke, charge create/void/refund, settings, accounts) are recorded append-only with actor + IP, viewable under **บันทึกกิจกรรม** or `GET /dashboard/audit-logs`. |
| **Migrations** | Schema is managed by **Alembic** (`backend/migrations/`). Apply with `alembic upgrade head`. After changing a model, generate a migration: `alembic revision --autogenerate -m "describe change"`, review it, then upgrade. |

---

## Tests

A pytest suite (82 tests) runs against a dedicated `panpay_test` Postgres database — it's
created automatically (the role needs `CREATEDB`), the schema is built per session, and each
test starts clean (tables truncated, rate limiter reset).

```bash
cd backend
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest
```

Covers: PromptPay QR/CRC, auth + rate limiting, charge creation/expiry, slip verification +
QR auto-decode + duplicate-slip guard, void/refund lifecycle, receiving accounts, settlement
fee math + payout, CSV/PDF reports, HMAC-signed webhooks (incl. delivery), the audit log, and
membership subscriptions (plans, recurring invoices, period advance, interval math).

## Project layout
```
backend/
  app/
    main.py            # FastAPI app + routers
    models.py          # SQLAlchemy models
    promptpay.py       # EMVCo PromptPay QR payload + CRC16
    slip_qr.py         # decode the QR embedded in a slip image (OpenCV)
    slip_verify.py     # pluggable verifiers (dev / SlipOK / EasySlip)
    charge_ops.py      # create / void / refund + account resolution
    settlement_ops.py  # settlement batching + fee math
    subscription_ops.py # plans, recurring invoices, coupons, proration
    notifications.py   # email/SMS bill + payment notifications
    jobs.py            # scheduled renewal/expiry job (CLI + scheduler)
    reports.py         # CSV builders
    pdf_receipt.py     # PDF receipts (reportlab, Thai font)
    ratelimit.py       # in-memory rate limiting
    audit.py           # append-only audit log
    webhooks.py        # HMAC-signed delivery with retries
    routers/           # auth, dashboard, charges, checkout, embed, membership, portal
  migrations/          # Alembic
  tests/               # pytest suite (Postgres test DB)
  seed.py              # demo merchant + API key
frontend/
  src/pages/           # Login, Register, Dashboard, Transactions, Members,
                       #   Settlements, ApiKeys, AuditLog, Settings, Checkout
  public/embed-demo.html
docker-compose.yml     # Postgres
dev.sh                 # run backend + frontend together
```
