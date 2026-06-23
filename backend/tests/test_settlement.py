from .helpers import create_charge, pay_charge


def _set_fee(client, headers, percent, fixed):
    client.patch("/dashboard/settings", headers=headers, json={"fee_percent": percent, "fee_fixed": fixed})


def _pay_n(client, headers, amounts):
    for amt in amounts:
        cid = create_charge(client, headers, amt)["id"]
        assert pay_charge(client, cid).status_code == 200


def test_generate_computes_fee_and_net(client, merchant):
    H = merchant["headers"]
    _set_fee(client, H, 1.5, 2)
    _pay_n(client, H, [100.0, 200.0, 300.0])
    s = client.post("/dashboard/settlements/generate", headers=H, json={}).json()
    assert s["charge_count"] == 3
    assert s["gross_amount"] == 600.0
    # 600 * 1.5% + 2 * 3 = 9 + 6 = 15
    assert s["fee_amount"] == 15.0
    assert s["net_amount"] == 585.0
    assert s["status"] == "pending"


def test_nothing_to_settle_returns_400(client, merchant):
    assert client.post("/dashboard/settlements/generate", headers=merchant["headers"], json={}).status_code == 400


def test_charges_not_double_settled(client, merchant):
    H = merchant["headers"]
    _pay_n(client, H, [50.0])
    assert client.post("/dashboard/settlements/generate", headers=H, json={}).status_code == 201
    # no remaining unsettled paid charges
    assert client.post("/dashboard/settlements/generate", headers=H, json={}).status_code == 400


def test_payout_and_double_payout(client, merchant):
    H = merchant["headers"]
    _pay_n(client, H, [100.0])
    sid = client.post("/dashboard/settlements/generate", headers=H, json={}).json()["id"]
    r = client.post(f"/dashboard/settlements/{sid}/payout", headers=H, json={"reference": "PO-1"})
    assert r.status_code == 200
    assert r.json()["status"] == "paid_out" and r.json()["reference"] == "PO-1" and r.json()["paid_out_at"]
    assert client.post(f"/dashboard/settlements/{sid}/payout", headers=H, json={}).status_code == 409


def test_settlement_csv_export(client, merchant):
    H = merchant["headers"]
    cid = create_charge(client, H, 70.0)["id"]
    pay_charge(client, cid)
    sid = client.post("/dashboard/settlements/generate", headers=H, json={}).json()["id"]
    r = client.get(f"/dashboard/settlements/{sid}/export.csv", headers=H)
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    assert cid in r.content.decode("utf-8")
