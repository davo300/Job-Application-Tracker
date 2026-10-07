"""Bounded, thread-safe per-process throttle for authentication endpoints.

Deploy a shared limiter at the reverse proxy before scaling to multiple workers.
Forwarded headers are intentionally not trusted for client identification.
"""

from collections import deque
from threading import Lock
from time import monotonic


class AuthRateLimiter:
    def __init__(self, attempts: int = 20, window: int = 60, max_clients: int = 10000):
        self.attempts = attempts
        self.window = window
        self.max_clients = max_clients
        self._clients: dict[str, deque[float]] = {}
        self._lock = Lock()

    def allow(self, client: str) -> bool:
        now = monotonic()
        with self._lock:
            expired = [
                key for key, times in self._clients.items() if times[-1] <= now - self.window
            ]
            for key in expired:
                del self._clients[key]
            if client not in self._clients:
                if len(self._clients) >= self.max_clients:
                    return False
                self._clients[client] = deque()
            times = self._clients[client]
            while times and times[0] <= now - self.window:
                times.popleft()
            if len(times) >= self.attempts:
                return False
            times.append(now)
            return True
