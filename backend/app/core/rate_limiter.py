"""
Zero-Dependency In-Memory Rate Limiter for VirtualFit AI.

Features:
- Sliding-window timestamp algorithm per client IP.
- Enforces strict request throttling on brute-force sensitive endpoints (e.g. /api/auth/login, /api/auth/register).
- Returns standard HTTP 429 Too Many Requests with RFC-compliant 'Retry-After' header.
- Automatic opportunistic cleanup of expired entries to prevent unbounded memory growth.
- Zero external dependencies: pure Python standard library (time, threading, typing).
- Easily configurable via environment variables and dependency factories.
"""
import os
import time
import logging
import threading
from typing import Dict, List, Optional
from fastapi import Request, HTTPException, status

logger = logging.getLogger("virtualfit.security.ratelimit")

# Global lock for thread-safe in-memory operations across worker threads
_rate_limit_lock = threading.Lock()
# Storage format: { "client_key": [timestamp1, timestamp2, ...] }
_request_records: Dict[str, List[float]] = {}
# Last cleanup timestamp
_last_cleanup_timestamp: float = time.time()
CLEANUP_INTERVAL_SECONDS: float = 300.0  # Cleanup every 5 minutes


def is_rate_limiting_enabled() -> bool:
    """Checks whether rate limiting is active via environment configuration."""
    val = os.getenv("RATE_LIMIT_ENABLED", "true").strip().lower()
    return val not in ("false", "0", "no", "disabled")


def get_client_ip(request: Request) -> str:
    """
    Extracts the client IP address from the incoming request.
    Inspects X-Forwarded-For if behind a reverse proxy (e.g. Nginx),
    falling back to request.client.host.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        # First IP in comma-separated list is the original client
        return forwarded.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown_client"


def cleanup_stale_records(cutoff: float) -> None:
    """
    Removes entries from _request_records where all timestamps are older than cutoff.
    Must be called while holding _rate_limit_lock.
    """
    stale_keys = []
    for key, timestamps in _request_records.items():
        # Keep only timestamps >= cutoff
        active = [t for t in timestamps if t >= cutoff]
        if not active:
            stale_keys.append(key)
        else:
            _request_records[key] = active
    for key in stale_keys:
        del _request_records[key]


class RateLimiter:
    """
    FastAPI dependency implementing a sliding-window rate limit.
    
    Usage:
        @router.post("/login", dependencies=[Depends(RateLimiter(max_requests=5, window_seconds=60))])
    """

    def __init__(
        self,
        max_requests: int = 5,
        window_seconds: int = 60,
        scope: str = "default",
    ):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.scope = scope

    def __call__(self, request: Request) -> None:
        if not is_rate_limiting_enabled():
            return

        client_ip = get_client_ip(request)
        key = f"{self.scope}:{client_ip}"
        now = time.time()
        window_start = now - self.window_seconds

        global _last_cleanup_timestamp

        with _rate_limit_lock:
            # Opportunistic cleanup of stale keys
            if now - _last_cleanup_timestamp > CLEANUP_INTERVAL_SECONDS:
                cleanup_stale_records(now - 3600.0)
                _last_cleanup_timestamp = now

            timestamps = _request_records.get(key, [])
            # Filter timestamps within current sliding window
            timestamps = [t for t in timestamps if t > window_start]

            if len(timestamps) >= self.max_requests:
                oldest_in_window = timestamps[0]
                retry_after = max(1, int(oldest_in_window + self.window_seconds - now))
                logger.warning(
                    f"Rate limit exceeded for client '{client_ip}' on scope '{self.scope}'. "
                    f"Count={len(timestamps)}/{self.max_requests} in {self.window_seconds}s. Retry-After: {retry_after}s"
                )
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Too many attempts from this IP address. Please wait {retry_after} seconds before trying again.",
                    headers={"Retry-After": str(retry_after)},
                )

            # Record this valid request
            timestamps.append(now)
            _request_records[key] = timestamps


def reset_rate_limits() -> None:
    """Helper for test suites to clear all recorded rate-limit history."""
    with _rate_limit_lock:
        _request_records.clear()

