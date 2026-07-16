from contextlib import asynccontextmanager


@asynccontextmanager
async def maybe_transaction(mongo_client):
    """Open a real MongoDB multi-document transaction when the client supports it, yielding the
    session to pass as `session=` on every read/write that must be atomic with the others.

    Requires a replica set (Atlas satisfies this automatically). mongomock-motor — the only
    MongoDB available in this repo's test environment (see tests/conftest.py) — raises
    NotImplementedError on start_session(), so tests instead exercise the compensating-rollback
    fallback path (session=None) at call sites that need one. See NOTES_schema_audit.md §9.
    """
    try:
        async with await mongo_client.start_session() as session:
            async with session.start_transaction():
                yield session
    except NotImplementedError:
        yield None
