import asyncio

from app.idempotency import MemoryIdempotencyStore


def test_memory_store_reserves_replays_and_detects_payload_conflicts():
    async def scenario():
        store = MemoryIdempotencyStore()
        assert await store.reserve("key", "fingerprint") == ("new", None)
        assert await store.reserve("key", "fingerprint") == ("pending", None)
        assert await store.reserve("key", "different") == ("conflict", None)
        await store.complete("key", "fingerprint", {"accepted": True})
        assert await store.reserve("key", "fingerprint") == ("complete", {"accepted": True})
        await store.aclose()

    asyncio.run(scenario())


def test_unknown_outcome_is_fail_closed_and_release_only_removes_pending():
    async def scenario():
        store = MemoryIdempotencyStore()
        await store.reserve("unknown", "same")
        await store.mark_unknown("unknown", "same")
        assert await store.reserve("unknown", "same") == ("unknown", None)
        await store.release("unknown", "same")
        assert await store.reserve("unknown", "same") == ("unknown", None)

        await store.reserve("pending", "same")
        await store.release("pending", "same")
        assert await store.reserve("pending", "same") == ("new", None)
        await store.aclose()

    asyncio.run(scenario())

def test_redis_store_encrypts_cached_response_and_replays_safely():
    import json
    from cryptography.fernet import Fernet
    from app.idempotency import RedisIdempotencyStore

    class FakeRedis:
        def __init__(self):
            self.values = {}
        async def set(self, key, value, ex=None, nx=False):
            if nx and key in self.values:
                return False
            self.values[key] = value
            return True
        async def get(self, key):
            return self.values.get(key)
        async def eval(self, script, count, key, fingerprint):
            raw = self.values.get(key)
            if raw is None:
                return 0
            record = json.loads(raw)
            if record.get("fingerprint") == fingerprint and record.get("status") == "pending":
                del self.values[key]
                return 1
            return 0
        async def ping(self):
            return True
        async def aclose(self):
            return None

    async def scenario():
        key = Fernet.generate_key().decode("ascii")
        store = RedisIdempotencyStore.__new__(RedisIdempotencyStore)
        store._redis = FakeRedis()
        store._ttl = 3600
        store._fernet = Fernet(key.encode("ascii"))
        assert await store.reserve("redis-key", "fp") == ("new", None)
        response = {"taxpayer": {"pin": "A123456789Z"}, "name": "Private Name"}
        await store.complete("redis-key", "fp", response)
        raw = store._redis.values["kra:idempotency:redis-key"]
        assert "Private Name" not in raw
        assert "A123456789Z" not in raw
        assert await store.reserve("redis-key", "fp") == ("complete", response)
        assert await store.reserve("redis-key", "other") == ("conflict", None)
        await store.aclose()

    asyncio.run(scenario())


def test_memory_rate_limit_is_shared_with_idempotency_store():
    async def scenario():
        store = MemoryIdempotencyStore()
        assert await store.allow_rate_limit("client", 2) is True
        assert await store.allow_rate_limit("client", 2) is True
        assert await store.allow_rate_limit("client", 2) is False
        assert await store.allow_rate_limit("other-client", 2) is True
        await store.aclose()

    asyncio.run(scenario())

def test_redis_rate_limit_uses_atomic_server_clock_window():
    from app.idempotency import RedisIdempotencyStore

    class FakeRedis:
        def __init__(self):
            self.now = 120_000
            self.hits = {}
        async def eval(self, script, key_count, key, window_ms, limit, member):
            assert "redis.call('TIME')" in script
            recent = [stamp for stamp, _ in self.hits.get(key, []) if self.now - stamp < int(window_ms)]
            if len(recent) >= int(limit):
                self.hits[key] = [(stamp, item) for stamp, item in self.hits[key] if self.now - stamp < int(window_ms)]
                return 0
            recent.append(self.now)
            self.hits[key] = [(stamp, item) for stamp, item in self.hits.get(key, []) if self.now - stamp < int(window_ms)] + [(self.now, member)]
            return 1

    async def scenario():
        store = RedisIdempotencyStore.__new__(RedisIdempotencyStore)
        store._redis = FakeRedis()
        assert await store.allow_rate_limit("client", 2) is True
        assert await store.allow_rate_limit("client", 2) is True
        assert await store.allow_rate_limit("client", 2) is False
        assert await store.allow_rate_limit("other", 2) is True

    asyncio.run(scenario())
