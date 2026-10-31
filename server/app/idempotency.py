"""Durable idempotency storage with a safe in-memory development fallback.

Redis is required for production. Keys are hashed by the caller; payload
fingerprints and cached response bodies are stored only in the protected
Redis instance and expire after the configured retention window.
"""
from __future__ import annotations

import asyncio
import json
import time
import uuid
from typing import Any, Protocol


class Store(Protocol):
    async def reserve(self, key: str, fingerprint: str) -> tuple[str, dict[str, Any] | None]: ...
    async def allow_rate_limit(self, identity: str, limit: int, window_seconds: int = 60) -> bool: ...
    async def complete(self, key: str, fingerprint: str, response: dict[str, Any]) -> None: ...
    async def mark_unknown(self, key: str, fingerprint: str) -> None: ...
    async def release(self, key: str, fingerprint: str) -> None: ...
    async def ping(self) -> None: ...
    async def aclose(self) -> None: ...


class MemoryIdempotencyStore:
    """Single-process fallback for local development and deterministic tests."""

    def __init__(self) -> None:
        self._entries: dict[str, dict[str, Any]] = {}
        self._hits: dict[str, list[float]] = {}
        self._lock = asyncio.Lock()

    async def reserve(self, key: str, fingerprint: str) -> tuple[str, dict[str, Any] | None]:
        async with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                self._entries[key] = {"fingerprint": fingerprint, "status": "pending"}
                return "new", None
            return self._interpret(entry, fingerprint)

    @staticmethod
    def _interpret(entry: dict[str, Any], fingerprint: str) -> tuple[str, dict[str, Any] | None]:
        if entry["fingerprint"] != fingerprint:
            return "conflict", None
        if entry["status"] == "complete":
            return "complete", entry["response"]
        if entry["status"] == "unknown":
            return "unknown", None
        return "pending", None

    async def allow_rate_limit(self, identity: str, limit: int, window_seconds: int = 60) -> bool:
        now = time.monotonic()
        async with self._lock:
            hits = [stamp for stamp in self._hits.get(identity, []) if now - stamp < window_seconds]
            if len(hits) >= limit:
                self._hits[identity] = hits
                return False
            hits.append(now)
            self._hits[identity] = hits
            return True

    async def complete(self, key: str, fingerprint: str, response: dict[str, Any]) -> None:
        async with self._lock:
            self._entries[key] = {"fingerprint": fingerprint, "status": "complete", "response": response}

    async def mark_unknown(self, key: str, fingerprint: str) -> None:
        async with self._lock:
            self._entries[key] = {"fingerprint": fingerprint, "status": "unknown"}

    async def release(self, key: str, fingerprint: str) -> None:
        async with self._lock:
            entry = self._entries.get(key)
            if entry and entry.get("fingerprint") == fingerprint and entry.get("status") == "pending":
                self._entries.pop(key, None)

    async def ping(self) -> None:
        return None

    async def aclose(self) -> None:
        return None


class RedisIdempotencyStore:
    """Cross-worker idempotency store backed by redis.asyncio."""

    def __init__(self, url: str, encryption_key: str, ttl_seconds: int = 604800) -> None:
        from cryptography.fernet import Fernet
        from redis.asyncio import Redis

        self._redis = Redis.from_url(url, decode_responses=True, socket_connect_timeout=3, socket_timeout=3)
        self._ttl = ttl_seconds
        self._fernet = Fernet(encryption_key.encode("ascii"))

    async def reserve(self, key: str, fingerprint: str) -> tuple[str, dict[str, Any] | None]:
        redis_key = f"kra:idempotency:{key}"
        pending = json.dumps({"fingerprint": fingerprint, "status": "pending"}, separators=(",", ":"))
        if await self._redis.set(redis_key, pending, ex=self._ttl, nx=True):
            return "new", None
        raw = await self._redis.get(redis_key)
        if raw is None:
            # The key expired between SET NX and GET. Retry reservation once.
            if await self._redis.set(redis_key, pending, ex=self._ttl, nx=True):
                return "new", None
            raw = await self._redis.get(redis_key)
        if raw is None:
            return "pending", None
        try:
            entry = json.loads(raw)
            if entry.get("fingerprint") != fingerprint:
                return "conflict", None
            if entry.get("status") == "complete":
                encrypted = entry.get("response_encrypted")
                if not isinstance(encrypted, str):
                    return "unknown", None
                response = json.loads(self._fernet.decrypt(encrypted.encode("ascii")))
                return "complete", response
            return MemoryIdempotencyStore._interpret(entry, fingerprint)
        except Exception:
            # Corrupt or undecryptable state must never permit a duplicate write.
            return "unknown", None

    async def allow_rate_limit(self, identity: str, limit: int, window_seconds: int = 60) -> bool:
        now_ms = time.time_ns() // 1_000_000
        window_ms = window_seconds * 1000
        member = f"{now_ms}:{uuid.uuid4().hex}"
        script = """
        redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', ARGV[1] - ARGV[2])
        local count = redis.call('ZCARD', KEYS[1])
        if count >= tonumber(ARGV[3]) then return 0 end
        redis.call('ZADD', KEYS[1], ARGV[1], ARGV[4])
        redis.call('PEXPIRE', KEYS[1], ARGV[2])
        return 1
        """
        result = await self._redis.eval(
            script, 1, f"kra:ratelimit:{identity}", now_ms, window_ms, limit, member
        )
        return bool(result)

    async def complete(self, key: str, fingerprint: str, response: dict[str, Any]) -> None:
        plaintext = json.dumps(response, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        encrypted = self._fernet.encrypt(plaintext).decode("ascii")
        value = json.dumps(
            {"fingerprint": fingerprint, "status": "complete", "response_encrypted": encrypted},
            separators=(",", ":"),
        )
        await self._redis.set(f"kra:idempotency:{key}", value, ex=self._ttl)

    async def mark_unknown(self, key: str, fingerprint: str) -> None:
        value = json.dumps({"fingerprint": fingerprint, "status": "unknown"}, separators=(",", ":"))
        await self._redis.set(f"kra:idempotency:{key}", value, ex=self._ttl)

    async def release(self, key: str, fingerprint: str) -> None:
        redis_key = f"kra:idempotency:{key}"
        script = """
        local raw = redis.call('GET', KEYS[1])
        if not raw then return 0 end
        local ok, value = pcall(cjson.decode, raw)
        if ok and value['fingerprint'] == ARGV[1] and value['status'] == 'pending' then
          return redis.call('DEL', KEYS[1])
        end
        return 0
        """
        await self._redis.eval(script, 1, redis_key, fingerprint)

    async def ping(self) -> None:
        await self._redis.ping()

    async def aclose(self) -> None:
        await self._redis.aclose()
