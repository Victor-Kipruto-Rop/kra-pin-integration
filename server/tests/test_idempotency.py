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
