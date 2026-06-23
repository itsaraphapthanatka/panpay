from .helpers import create_charge, pay_charge


def test_csv_export_has_bom_and_rows(client, merchant):
    H = merchant["headers"]
    cid = create_charge(client, H, 100.0, reference="ord-9")["id"]
    pay_charge(client, cid)
    r = client.get("/dashboard/charges/export.csv", headers=H)
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    assert "attachment" in r.headers["content-disposition"]
    body = r.content.decode("utf-8")
    assert body.startswith("﻿")  # UTF-8 BOM
    assert "charge_id,reference,description,amount" in body
    assert cid in body and "ord-9" in body


def test_pdf_receipt_bytes(client, merchant):
    cid = create_charge(client, merchant["headers"], 100.0)["id"]
    pay_charge(client, cid)
    r = client.get(f"/checkout/{cid}/receipt.pdf")
    assert r.status_code == 200
    assert r.content[:5] == b"%PDF-"
    assert len(r.content) > 1500


def test_thai_font_resolves():
    from app.pdf_receipt import _ensure_font

    # Returns a registered font name (PanThai on a machine with a Thai TTF, else Helvetica)
    assert _ensure_font() in ("PanThai", "Helvetica")
