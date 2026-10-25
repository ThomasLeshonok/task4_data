import pytest

from security.auth import check_credentials, hash_password, verify_password
from security.limits import RateLimiter, client_ip

def test_hash_roundtrip():
    stored = hash_password("correct horse battery")
    assert verify_password("correct horse battery", stored)
    assert not verify_password("wrong", stored)
    assert hash_password("same") != hash_password("same")

def test_check_credentials(monkeypatch):
    monkeypatch.setenv("APP_PASSWORD_HASH", hash_password("s3cret-password"))
    monkeypatch.delenv("APP_USERNAME", raising=False)
    assert check_credentials("Customer", "s3cret-password")
    assert not check_credentials("customer", "s3cret-password")
    assert not check_credentials("Customer", "nope")

def test_fails_closed_without_hash(monkeypatch):
    monkeypatch.delenv("APP_PASSWORD_HASH", raising=False)
    assert not check_credentials("Customer", "")

@pytest.mark.parametrize("bad", ["", "plain", "md5:aa:bb", "scrypt:zz:bb"])
def test_malformed_hash_rejects(bad):
    assert not verify_password("x", bad)

def test_rate_limiter_window():
    now = [0.0]
    limiter = RateLimiter(2, 60, clock=lambda: now[0])
    assert limiter.hit("a")[0] and limiter.hit("a")[0]
    allowed, wait = limiter.hit("a")
    assert not allowed and 0 < wait <= 61
    assert limiter.hit("b")[0]
    now[0] = 61
    assert limiter.hit("a")[0]

def test_check_does_not_count():
    limiter = RateLimiter(1, 60)
    assert limiter.check("a")[0] and limiter.check("a")[0]
    limiter.hit("a")
    assert not limiter.check("a")[0]
    limiter.reset("a")
    assert limiter.check("a")[0]

@pytest.mark.parametrize("headers, expected", [
    ({"X-Client-IP": "203.0.113.7"}, "203.0.113.7"),
    ({"X-Forwarded-For": "1.1.1.1, 203.0.113.7:51234"}, "203.0.113.7"),
    ({"X-Forwarded-For": "[2001:db8::1]:443"}, "2001:db8::1"),
    ({"X-Forwarded-For": "2001:db8::1"}, "2001:db8::1"),
    ({}, "local"),
])
def test_client_ip(headers, expected):
    assert client_ip(headers) == expected
