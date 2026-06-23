"""CSV report builders. Output includes a UTF-8 BOM so Excel renders Thai correctly."""

import csv
import io

from .models import Charge, Settlement

_BOM = "﻿"


def _iso(dt) -> str:
    return dt.isoformat() if dt else ""


def charges_csv(charges: list[Charge]) -> str:
    out = io.StringIO()
    out.write(_BOM)
    w = csv.writer(out)
    w.writerow([
        "charge_id", "reference", "description", "amount", "currency", "status",
        "created_at", "paid_at", "trans_ref", "sender_name", "sender_bank",
        "refunded_at", "refund_reason",
    ])
    for c in charges:
        p = c.payment
        w.writerow([
            c.id, c.reference or "", c.description or "", f"{float(c.amount):.2f}", c.currency, c.status,
            _iso(c.created_at), _iso(c.paid_at),
            (p.trans_ref if p else ""), (p.sender_name if p else ""), (p.sender_bank if p else ""),
            _iso(c.refunded_at), c.refund_reason or "",
        ])
    return out.getvalue()


def settlement_csv(settlement: Settlement, charges: list[Charge]) -> str:
    out = io.StringIO()
    out.write(_BOM)
    w = csv.writer(out)
    w.writerow(["settlement_id", settlement.id])
    w.writerow(["status", settlement.status])
    w.writerow(["gross", f"{float(settlement.gross_amount):.2f}"])
    w.writerow(["fee", f"{float(settlement.fee_amount):.2f}"])
    w.writerow(["net", f"{float(settlement.net_amount):.2f}"])
    w.writerow(["charge_count", settlement.charge_count])
    w.writerow([])
    w.writerow(["charge_id", "reference", "amount", "paid_at", "trans_ref"])
    for c in charges:
        w.writerow([
            c.id, c.reference or "", f"{float(c.amount):.2f}", _iso(c.paid_at),
            (c.payment.trans_ref if c.payment else ""),
        ])
    return out.getvalue()
