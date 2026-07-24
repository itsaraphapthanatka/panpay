# PanPay LINE bridge (experimental)

Logs into a LINE account with [`@evex/linejs`](https://github.com/evex-dev/linejs)
(a **SelfBot** library), reads incoming bank "money in" notification messages,
parses the amount, and reports it to PanPay — which matches it to a single
pending charge of that amount and marks it paid.

> ## ⚠️ Read this first
> - **SelfBots violate LINE's Terms of Service.** The LINE account you log in with
>   can be **permanently banned**. Use a throwaway/secondary account, never your main one.
> - It's **unofficial & reverse-engineered** — LINE protocol changes break it often.
> - **Amount-only matching is ambiguous** (two charges of the same amount → no match)
>   and notification text can be **spoofed**. This is a convenience signal, **not**
>   authoritative verification.
> - **Slip verification (SlipOK/EasySlip) remains the source of truth.** Treat this
>   bridge as an optional extra, and keep it isolated from the core gateway.

## How it works

```
LINE account (receives bank transfer alerts)
   │  @evex/linejs SelfBot reads messages
   ▼
parser.mjs  →  { amount }
   │  POST /v1/line/transfer  (Authorization: Bearer sk_live_...)
   ▼
PanPay backend → match ONE pending charge of that amount → mark paid (+ webhook)
```

## Setup

```bash
cd line-bridge
npx jsr add @evex/linejs        # installs the LINE client (already in package.json)
cp .env.example .env            # set PANPAY_URL + PANPAY_API_KEY (a merchant sk_live_ key)
npm start                       # first run prints a QR / PIN — log in the LINE account
```

On first run it prints a **QR code / PIN** — scan/confirm it with the LINE app of the
account that receives your bank's transfer notifications. The auth token is cached in
`storage.json` (gitignored) so later runs resume without scanning.

## Test

```bash
npm test     # unit-tests the bank-notification parser (no LINE login needed)
```

## Notes
- The backend endpoint (`POST /v1/line/transfer`) is matched per-merchant via the API key,
  matches only an **exact, unique** pending amount within the last 24h, and is **idempotent**
  per LINE message id. Ambiguous/zero matches are reported back, not force-paid.
- linejs API field names (`op.message.id`, `msg.text`, `msg.from`) can change between
  versions — "when in doubt, read the source" (the library updates frequently).
