# test_auth.py
import pytest
from app import app


@pytest.fixture
def client():
    """
    Creates a fresh test client for each test.
    """
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret"

    with app.test_client() as client:
        yield client


# -------------------------
# LOGIN TESTS
# -------------------------

def test_login_success(client):
    res = client.post("/login", json={
        "username": "admin",
        "password": "pass"
    })

    assert res.status_code == 200


def test_login_wrong_password(client):
    res = client.post("/login", json={
        "username": "admin",
        "password": "wrong"
    })

    assert res.status_code == 401


def test_login_unknown_user(client):
    res = client.post("/login", json={
        "username": "ghost",
        "password": "pass"
    })

    assert res.status_code == 401


def test_login_sets_session(client):
    client.post("/login", json={
        "username": "admin",
        "password": "pass"
    })

    with client.session_transaction() as sess:
        assert "user_id" in sess


# -------------------------
# PROTECTED ROUTE TESTS
# -------------------------

def test_protected_requires_login(client):
    res = client.get("/protected")
    assert res.status_code == 401


def test_protected_after_login(client):
    client.post("/login", json={
        "username": "admin",
        "password": "pass"
    })

    res = client.get("/protected")
    assert res.status_code == 200


def test_protected_fails_if_session_cleared(client):
    client.post("/login", json={
        "username": "admin",
        "password": "pass"
    })

    with client.session_transaction() as sess:
        sess.clear()

    res = client.get("/protected")
    assert res.status_code == 401


# -------------------------
# OPTIONAL: LOGOUT TEST
# -------------------------


def test_logout(client):
    client.post("/login", json={
        "username": "admin",
        "password": "pass"
    })

    client.post("/logout")

    res = client.get("/protected")
    assert res.status_code == 401
