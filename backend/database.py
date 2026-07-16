import os

from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from config import settings

# URL.create() (not an f-string DSN) is deliberate: it correctly percent-encodes special
# characters in the password (this app's dev password contains a literal "@", which would be
# mis-parsed as the user/host separator in a naive "mysql+aiomysql://user:pass@host/db" string).
_url = URL.create(
    drivername="mysql+aiomysql",
    username=settings.mysql_user,
    password=settings.mysql_password,
    host=settings.mysql_host,
    port=settings.mysql_port,
    database=settings.mysql_database,
)

# pytest calls asyncio.run() once per fixture/test (a fresh event loop each time), and
# TestClient's own portal runs yet another loop — a pooled connection created on one loop can't
# safely be reused on another (surfaces as "NoneType has no attribute 'send'" on Windows'
# Proactor loop, or "Future attached to a different loop" elsewhere). NullPool opens a fresh raw
# connection per checkout instead of reusing one across loops. This is a testing-only concern:
# a real uvicorn process keeps one event loop for its whole lifetime, so production keeps the
# normal pooled engine. See tests/conftest.py, which sets this before importing anything.
_testing = os.environ.get("TESTING") == "1"

_engine_kwargs = {"echo": settings.sql_echo}
if _testing:
    _engine_kwargs["poolclass"] = NullPool
else:
    _engine_kwargs["pool_pre_ping"] = True   # detect stale connections — MySQL's wait_timeout drops idle ones
    _engine_kwargs["pool_recycle"] = 3600    # recycle connections before that happens

engine = create_async_engine(_url, **_engine_kwargs)

# expire_on_commit=False: several call sites read attributes off a just-committed object without
# an explicit re-fetch (matches how the app read a dict back immediately after insert_one under
# Mongo) — the SQLAlchemy default would force a surprise re-SELECT on next attribute access.
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


async def get_db():
    """Request-scoped session. Commits on clean exit, rolls back on exception — SQLAlchemy
    sessions do NOT auto-commit like Motor's client did, so this is baked into the dependency
    itself rather than left for each route to remember."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
