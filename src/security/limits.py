import math
import os
import threading
import time
from collections import deque
from dataclasses import dataclass

class RateLimiter:
    def __init__(self, limit: int, window_seconds: float, clock=time.monotonic):
        self.limit = limit
        self.window = window_seconds
        self.clock = clock
        self._hits: dict[str, deque] = {}
        self._lock = threading.Lock()
        self._calls = 0

    def _prune(self, key: str, now: float) -> deque:
        hits = self._hits.setdefault(key, deque())
        while hits and now - hits[0] >= self.window:
            hits.popleft()
        return hits

    def _retry_after(self, hits: deque, now: float) -> int:
        return max(1, math.ceil(self.window - (now - hits[0])))

    def check(self, key: str) -> tuple[bool, int]:
        with self._lock:
            now = self.clock()
            hits = self._prune(key, now)
            return (True, 0) if len(hits) < self.limit else (False, self._retry_after(hits, now))

    def hit(self, key: str) -> tuple[bool, int]:
        with self._lock:
            now = self.clock()
            hits = self._prune(key, now)
            if len(hits) >= self.limit:
                return False, self._retry_after(hits, now)
            hits.append(now)
            self._calls += 1
            if self._calls % 1000 == 0:
                self._drop_idle(now)
            return True, 0

    def reset(self, key: str) -> None:
        with self._lock:
            self._hits.pop(key, None)

    def _drop_idle(self, now: float) -> None:
        for key in [k for k, v in self._hits.items() if not v or now - v[-1] >= self.window]:
            del self._hits[key]

def _env_int(name: str, default: int) -> int:
    return int(os.environ.get(name, default))

@dataclass
class Limits:
    sessions: RateLimiter
    login_failures: RateLimiter
    questions_per_ip: RateLimiter
    questions_total: RateLimiter
    question_max_chars: int

    @classmethod
    def from_env(cls) -> "Limits":
        return cls(
            sessions=RateLimiter(_env_int("LIMIT_SESSIONS_PER_IP_10MIN", 30), 600),
            login_failures=RateLimiter(_env_int("LIMIT_LOGIN_FAILURES_15MIN", 5), 900),
            questions_per_ip=RateLimiter(_env_int("LIMIT_QUESTIONS_PER_IP_HOUR", 20), 3600),
            questions_total=RateLimiter(_env_int("LIMIT_QUESTIONS_PER_DAY", 500), 86400),
            question_max_chars=_env_int("LIMIT_QUESTION_CHARS", 500),
        )

def _strip_port(address: str) -> str:
    address = address.strip()
    if address.startswith("["):
        return address[1:].split("]")[0]
    return address.rsplit(":", 1)[0] if address.count(":") == 1 else address

def client_ip(headers, fallback: str | None = None) -> str:
    headers = {k.lower(): v for k, v in (headers or {}).items()}
    if headers.get("x-client-ip"):
        return _strip_port(headers["x-client-ip"])
    forwarded = [p for p in headers.get("x-forwarded-for", "").split(",") if p.strip()]
    if forwarded:
        return _strip_port(forwarded[-1])
    return fallback or "local"
