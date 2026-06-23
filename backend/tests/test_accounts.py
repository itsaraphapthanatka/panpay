def _add(client, headers, name, pp, is_default=False):
    return client.post("/dashboard/receiving-accounts", headers=headers,
                       json={"name": name, "promptpay_id": pp, "is_default": is_default})


def test_first_account_is_default(client, merchant):
    a = _add(client, merchant["headers"], "A", "0811111111").json()
    assert a["is_default"] is True


def test_charge_uses_selected_account(client, merchant):
    H = merchant["headers"]
    _add(client, H, "A", "0811111111")
    b = _add(client, H, "B", "0822222222").json()
    cid = client.post("/dashboard/charges", headers=H, json={"amount": 50, "account_id": b["id"]}).json()["id"]
    qr = client.get(f"/checkout/{cid}").json()["qr_payload"]
    assert "0066822222222" in qr


def test_charge_defaults_to_default_account(client, merchant):
    H = merchant["headers"]
    a = _add(client, H, "A", "0811111111").json()
    _add(client, H, "B", "0822222222")
    # A is default (first); a charge with no account_id uses it
    cid = client.post("/dashboard/charges", headers=H, json={"amount": 50}).json()["id"]
    qr = client.get(f"/checkout/{cid}").json()["qr_payload"]
    assert "0066811111111" in qr
    assert a["is_default"] is True


def test_set_default_and_delete(client, merchant):
    H = merchant["headers"]
    a = _add(client, H, "A", "0811111111").json()
    b = _add(client, H, "B", "0822222222").json()
    client.post(f"/dashboard/receiving-accounts/{b['id']}/default", headers=H)
    accts = {x["id"]: x for x in client.get("/dashboard/receiving-accounts", headers=H).json()}
    assert accts[b["id"]]["is_default"] is True
    assert accts[a["id"]]["is_default"] is False
    assert client.delete(f"/dashboard/receiving-accounts/{a['id']}", headers=H).status_code == 204


def test_unknown_account_rejected(client, merchant):
    r = client.post("/dashboard/charges", headers=merchant["headers"], json={"amount": 10, "account_id": "rcv_nope"})
    assert r.status_code == 400
