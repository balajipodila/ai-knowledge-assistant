import asyncio
import hashlib
import math
from collections import deque
from collections.abc import Iterator
from dataclasses import dataclass
from ipaddress import ip_address, ip_network
from threading import Lock
from time import monotonic

from fastapi import Depends, Request

from app.core.auth import get_current_user
from app.core.config import Settings, get_settings
from app.models.user import User

_MINUTE_SECONDS = 60
_DAY_SECONDS = 24 * 60 * 60


class RateLimitExceeded(Exception):
    def __init__(self, retry_after_seconds: int) -> None:
        self.retry_after_seconds = max(1, retry_after_seconds)
        self.code = "TOO_MANY_REQUESTS"
        self.message = "Too many requests. Please try again later."


@dataclass(frozen=True)
class _Rule:
    scope: str
    identity: str
    limit: int
    window_seconds: int


class RequestRateLimiter:
    def __init__(
        self,
        *,
        cleanup_interval_seconds: int = 60,
        clock=monotonic,
    ) -> None:
        self.cleanup_interval_seconds = cleanup_interval_seconds
        self._clock = clock
        self._lock = Lock()
        self._events: dict[tuple[str, int, int], deque[float]] = {}
        self._concurrent: dict[str, int] = {}
        self._last_cleanup = 0.0

    @staticmethod
    def _hashed_key(scope: str, identity: str) -> str:
        digest = hashlib.blake2s(
            identity.encode("utf-8", errors="replace"), digest_size=16
        ).hexdigest()
        return f"{scope}:{digest}"

    def consume(self, rules: list[_Rule]) -> None:
        now = self._clock()
        retry_after = 0
        with self._lock:
            if now - self._last_cleanup >= self.cleanup_interval_seconds:
                self._cleanup_locked(now)

            active: list[tuple[_Rule, deque[float]]] = []
            for rule in rules:
                bucket_id = self._hashed_key(rule.scope, rule.identity)
                bucket_key = (bucket_id, rule.limit, rule.window_seconds)
                events = self._events.setdefault(bucket_key, deque())
                cutoff = now - rule.window_seconds
                while events and events[0] <= cutoff:
                    events.popleft()
                if len(events) >= rule.limit:
                    retry_after = max(
                        retry_after,
                        math.ceil(events[0] + rule.window_seconds - now),
                    )
                active.append((rule, events))

            for rule, events in active:
                if len(events) < rule.limit:
                    events.append(now)

        if retry_after:
            raise RateLimitExceeded(retry_after)

    def try_acquire_concurrent(self, scope: str, identity: str, limit: int) -> bool:
        key = self._hashed_key(scope, identity)
        with self._lock:
            active = self._concurrent.get(key, 0)
            if active >= limit:
                return False
            self._concurrent[key] = active + 1
            return True

    def release_concurrent(self, scope: str, identity: str) -> None:
        key = self._hashed_key(scope, identity)
        with self._lock:
            active = self._concurrent.get(key, 0)
            if active <= 1:
                self._concurrent.pop(key, None)
            else:
                self._concurrent[key] = active - 1

    def cleanup_expired(self) -> None:
        with self._lock:
            self._cleanup_locked(self._clock())

    def _cleanup_locked(self, now: float) -> None:
        for key, events in list(self._events.items()):
            cutoff = now - key[2]
            while events and events[0] <= cutoff:
                events.popleft()
            if not events:
                del self._events[key]
        self._last_cleanup = now


def trusted_client_ip(request: Request, settings: Settings) -> str:
    peer = request.client.host if request.client is not None else "unknown"
    if not settings.trusted_proxy_cidrs:
        return peer
    try:
        peer_address = ip_address(peer)
        trusted_networks = [ip_network(cidr) for cidr in settings.trusted_proxy_cidrs]
    except ValueError:
        return peer
    if not any(peer_address in network for network in trusted_networks):
        return peer

    forwarded = request.headers.get("x-forwarded-for")
    if not forwarded:
        return peer
    try:
        chain = [ip_address(value.strip()) for value in forwarded.split(",")]
    except ValueError:
        return peer
    if not chain:
        return peer

    for address in reversed(chain):
        if not any(address in network for network in trusted_networks):
            return str(address)
    return str(chain[0])


def get_request_limiter(request: Request) -> RequestRateLimiter:
    return request.app.state.request_rate_limiter


def enforce_resource_rate_limit(
    request: Request,
    user: User,
    settings: Settings,
    resource: str,
) -> None:
    limits = {
        "chat": (
            settings.chat_requests_per_minute,
            settings.chat_requests_per_day,
        ),
        "upload": (
            settings.upload_requests_per_minute,
            settings.upload_requests_per_day,
        ),
        "search": (
            settings.search_requests_per_minute,
            settings.search_requests_per_day,
        ),
    }
    per_minute, per_day = limits[resource]
    get_request_limiter(request).consume(
        [
            _Rule(resource, str(user.id), per_minute, _MINUTE_SECONDS),
            _Rule(resource, str(user.id), per_day, _DAY_SECONDS),
        ]
    )


def enforce_auth_attempt(
    request: Request,
    *,
    email: str,
    action: str,
    settings: Settings,
) -> None:
    client_ip = trusted_client_ip(request, settings)
    normalized_email = email.strip().casefold()
    get_request_limiter(request).consume(
        [
            _Rule(
                f"auth:{action}:ip-email",
                f"{client_ip}|{normalized_email}",
                settings.auth_email_attempts_per_minute,
                _MINUTE_SECONDS,
            ),
            _Rule(
                f"auth:{action}:ip",
                client_ip,
                settings.auth_ip_attempts_per_minute,
                _MINUTE_SECONDS,
            ),
        ]
    )


def chat_rate_limit(
    request: Request,
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> Iterator[None]:
    limiter = get_request_limiter(request)
    enforce_resource_rate_limit(request, user, settings, "chat")
    user_key = str(user.id)
    if not limiter.try_acquire_concurrent(
        "chat-concurrent", user_key, settings.chat_concurrent_requests_per_user
    ):
        raise RateLimitExceeded(1)
    try:
        yield
    finally:
        limiter.release_concurrent("chat-concurrent", user_key)


def upload_rate_limit(
    request: Request,
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> None:
    enforce_resource_rate_limit(request, user, settings, "upload")


def search_rate_limit(
    request: Request,
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> None:
    enforce_resource_rate_limit(request, user, settings, "search")


async def cleanup_rate_limiter_periodically(
    limiter: RequestRateLimiter,
) -> None:
    while True:
        await asyncio.sleep(limiter.cleanup_interval_seconds)
        limiter.cleanup_expired()
