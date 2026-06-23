from .helpers import pay_charge


def _plan(client, headers, **over):
    body = {"name": "Gold", "amount": 299.0, "interval_unit": "month", "interval_count": 1, **over}
    return client.post("/dashboard/plans", headers=headers, json=body).json()


def _subscribe(client, headers, plan_id, name="A"):
    return client.post("/dashboard/subscriptions", headers=headers,
                       json={"plan_id": plan_id, "customer_name": name}).json()


def _token(sub_out) -> str:
    return sub_out["portal_url"].rsplit("/m/", 1)[1]


def test_portal_view_is_public_and_shows_open_invoice(client, merchant):
    H = merchant["headers"]
    created = _subscribe(client, H, _plan(client, H)["id"])
    token = _token(created["subscription"])

    r = client.get(f"/portal/{token}")  # no auth header
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["business_name"] == "Test Shop"
    assert body["plan_name"] == "Gold"
    assert body["status"] == "pending"
    assert len(body["invoices"]) == 1
    assert body["open_invoice_url"].endswith(f"/pay/{created['invoice']['id']}")


def test_portal_bad_token_404(client):
    assert client.get("/portal/mpt_nope").status_code == 404


def test_portal_renew_returns_open_then_issues_next(client, merchant):
    H = merchant["headers"]
    created = _subscribe(client, H, _plan(client, H)["id"])
    token = _token(created["subscription"])

    # while an invoice is open, renew returns that same invoice
    r1 = client.post(f"/portal/{token}/renew")
    assert r1.status_code == 200
    assert r1.json()["checkout_url"].endswith(f"/pay/{created['invoice']['id']}")

    # pay it -> active, no open invoice
    pay_charge(client, created["invoice"]["id"])
    assert client.get(f"/portal/{token}").json()["open_invoice_url"] is None
    assert client.get(f"/portal/{token}").json()["status"] == "active"

    # renew now issues a NEW invoice and the membership goes past_due
    r2 = client.post(f"/portal/{token}/renew")
    new_url = r2.json()["checkout_url"]
    assert not new_url.endswith(f"/pay/{created['invoice']['id']}")
    assert client.get(f"/portal/{token}").json()["status"] == "past_due"


def test_portal_renew_on_canceled_409(client, merchant):
    H = merchant["headers"]
    created = _subscribe(client, H, _plan(client, H)["id"])
    sub_id = created["subscription"]["id"]
    token = _token(created["subscription"])
    client.post(f"/dashboard/subscriptions/{sub_id}/cancel", headers=H)
    assert client.post(f"/portal/{token}/renew").status_code == 409


def test_subscription_stats_mrr_and_churn(client, merchant):
    H = merchant["headers"]
    monthly = _plan(client, H, name="M", amount=300, interval_unit="month", interval_count=1)
    yearly = _plan(client, H, name="Y", amount=1200, interval_unit="year", interval_count=1)

    s1 = _subscribe(client, H, monthly["id"], "m1")
    pay_charge(client, s1["invoice"]["id"])           # active, MRR +300
    s2 = _subscribe(client, H, yearly["id"], "y1")
    pay_charge(client, s2["invoice"]["id"])           # active, MRR +100 (1200/12)
    s3 = _subscribe(client, H, monthly["id"], "m2")
    pay_charge(client, s3["invoice"]["id"])           # active, MRR +300
    client.post(f"/dashboard/subscriptions/{s3['subscription']['id']}/cancel", headers=H)  # churn

    stats = client.get("/dashboard/subscription-stats", headers=H).json()
    assert stats["active_members"] == 2
    assert abs(stats["mrr"] - 400.0) < 0.01      # 300 + 100
    assert abs(stats["arr"] - 4800.0) < 0.01
    assert stats["new_this_month"] == 3          # m1 + y1 + m2 all activated this month (m2 later churned)
    assert stats["churned_this_month"] == 1      # m2 canceled
    assert stats["by_status"]["active"] == 2
    assert stats["by_status"]["canceled"] == 1
