import secrets


def _email():
    return f"a_{secrets.token_hex(4)}@panpay.io"


def test_register_returns_token(client):
    r = client.post("/auth/register", json={
        "email": _email(), "password": "secret123", "business_name": "Shop",
    })
    assert r.status_code == 200
    assert r.json()["access_token"]


def test_duplicate_email_rejected(client):
    email = _email()
    body = {"email": email, "password": "secret123", "business_name": "Shop"}
    assert client.post("/auth/register", json=body).status_code == 200
    assert client.post("/auth/register", json=body).status_code == 409


def test_login_success_and_failure(client):
    email = _email()
    client.post("/auth/register", json={"email": email, "password": "secret123", "business_name": "Shop"})
    assert client.post("/auth/login", json={"email": email, "password": "secret123"}).status_code == 200
    assert client.post("/auth/login", json={"email": email, "password": "wrong"}).status_code == 401


def test_me_requires_auth(client, merchant):
    assert client.get("/auth/me").status_code == 401
    r = client.get("/auth/me", headers=merchant["headers"])
    assert r.status_code == 200
    assert r.json()["email"] == merchant["email"]


def test_invalid_email_domain_rejected(client):
    r = client.post("/auth/register", json={
        "email": "x@reserved.local", "password": "secret123", "business_name": "Shop",
    })
    assert r.status_code == 422


def test_rate_limit_on_login(client):
    email = _email()
    client.post("/auth/register", json={"email": email, "password": "secret123", "business_name": "Shop"})
    codes = [
        client.post("/auth/login", json={"email": email, "password": "secret123"}).status_code
        for _ in range(24)
    ]
    assert 429 in codes
    assert codes.count(200) <= 20
