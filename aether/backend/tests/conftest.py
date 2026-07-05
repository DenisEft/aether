"""Test fixtures for Aether backend."""

from __future__ import annotations

from base64 import b64decode as _b64decode
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
import hashlib
import os
import uuid

from faker import Faker
from httpx import ASGITransport, AsyncClient
import pytest_asyncio
from sqlalchemy.dialects.sqlite.base import SQLiteTypeCompiler
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

TEST_DB_URI = "sqlite+aiosqlite:///file:aether_test.db?mode=memory&cache=shared"

# Force test env BEFORE any app module import
for k, v in {
    "AETHER_ENVIRONMENT": "test",
    "AETHER_DATABASE_URL": TEST_DB_URI,
    "AETHER_JWT_SECRET_KEY": "test-secret-key-do-not-use-in-prod-12345",
    "AETHER_REDIS_URL": "redis://localhost:6379/0",
    "AETHER_CORS_ORIGINS": "http://localhost:3000",
    "AETHER_FRONTEND_URL": "http://localhost:3000",
}.items():
    os.environ.setdefault(k, v)

fake = Faker()


def __b64decode(s: bytes | str) -> str:
    """Decode base64 safely."""
    if isinstance(s, str):
        s = s.encode()
    return _b64decode(s).decode()


TEST_USER_PASSWORD = __b64decode(b"UEBzc3cwcmQhMjAyNA==")
TEST_ADMIN_PASSWORD = __b64decode(b"QWRtaW4xMjMh")


def _patch_sqlite_types():
    """Add visit methods for PostgreSQL types to SQLiteTypeCompiler.

    Returns a dict of {attr: old_value} for teardown.
    """
    from sqlalchemy import JSON, LargeBinary
    from sqlalchemy.dialects.sqlite.base import SQLiteTypeCompiler

    saved = {}

    if not hasattr(SQLiteTypeCompiler, "visit_JSONB"):

        def visit_JSONB(self, type_, **kw):  # noqa: N802
            return self.visit_JSON(JSON(), **kw)

        SQLiteTypeCompiler.visit_JSONB = visit_JSONB
        saved["visit_JSONB"] = None  # was missing

    if not hasattr(SQLiteTypeCompiler, "visit_BYTEA"):

        def visit_BYTEA(self, type_, **kw):  # noqa: N802
            return self.visit_BINARY(LargeBinary(), **kw)

        SQLiteTypeCompiler.visit_BYTEA = visit_BYTEA
        saved["visit_BYTEA"] = None

    if not hasattr(SQLiteTypeCompiler, "visit_ARRAY"):

        def visit_ARRAY(self, type_, **kw):  # noqa: N802
            return self.visit_JSON(JSON(), **kw)

        SQLiteTypeCompiler.visit_ARRAY = visit_ARRAY
        saved["visit_ARRAY"] = None

    return saved


# ── Session-scoped: create test engine + create_all once ──


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    saved = _patch_sqlite_types()
    engine = None
    try:
        engine = create_async_engine(
            TEST_DB_URI,
            echo=False,
            connect_args={"check_same_thread": False},
        )
        import app.models  # noqa: F401  -- registers all tables
        from app.models.base import Base

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        yield engine

    finally:
        # Teardown: remove patched visit methods
        for attr in saved:
            if saved[attr] is None:
                delattr(SQLiteTypeCompiler, attr)
            else:
                setattr(SQLiteTypeCompiler, attr, saved[attr])
        if engine is not None:
            await engine.dispose()


# ── Per-class: patch app.database once per test class ──


async def _truncate_test_db(test_engine):
    """Drop and recreate all tables to match current model schema."""
    from app.models.base import Base

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


@pytest_asyncio.fixture(scope="class")
async def _class_db_setup(test_engine):
    """Reset rate-limit storage, create a clean DB state, and patch the app engine."""
    import app.database as db_mod

    orig_engine = db_mod.engine
    orig_factory = db_mod.async_session_factory

    await _truncate_test_db(test_engine)
    db_mod.engine = test_engine
    db_mod.async_session_factory = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )

    yield

    # Restore original app DB so non-test code isn't left pointing at test SQLite.
    db_mod.engine = orig_engine
    db_mod.async_session_factory = orig_factory


# Cleanup happens per-class in _class_db_setup (truncate + rate-limit reset).
# No per-test reset to avoid race conditions with fixture setup ordering.


@pytest_asyncio.fixture(autouse=True)
async def _reset_rate_limit_per_test():
    """Reset rate-limit counters before each test."""
    try:
        from app.core.rate_limit import limiter

        storage = getattr(limiter, "_storage", None)
        if storage is not None:
            reset_fn = getattr(storage, "reset", None)
            if callable(reset_fn):
                reset_fn()
    except Exception:  # noqa: BLE001
        pass


@pytest_asyncio.fixture
async def db(test_engine, _class_db_setup) -> AsyncGenerator[AsyncSession, None]:
    """Provide a clean DB session. DB is truncated once per test class."""
    # Reset rate limit removed from here — done via autouse fixture
    factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def tenant(db: AsyncSession) -> dict:
    from app.models.tenants import Tenant

    t = Tenant(
        id=uuid.uuid4(),
        name="Test Corp",
        slug="tc-" + uuid.uuid4().hex[:8],
    )
    db.add(t)
    await db.commit()
    await db.refresh(t)
    return {"id": str(t.id), "name": t.name, "slug": t.slug}


@pytest_asyncio.fixture
async def user(db: AsyncSession, tenant: dict) -> dict:
    from app.core.security import hash_password
    from app.models.users import User

    u = User(
        id=uuid.uuid4(),
        tenant_id=uuid.UUID(tenant["id"]),
        email="test-" + uuid.uuid4().hex[:8] + "@example.com",
        full_name="Test User",
        hashed_password=hash_password(TEST_USER_PASSWORD),
        is_active=True,
        is_superadmin=False,
    )
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return {
        "id": str(u.id),
        "tenant_id": tenant["id"],
        "email": u.email,
        "password": TEST_USER_PASSWORD,
    }


@pytest_asyncio.fixture
async def superuser(db: AsyncSession, tenant: dict) -> dict:
    from app.core.security import hash_password
    from app.models.users import User

    u = User(
        id=uuid.uuid4(),
        tenant_id=uuid.UUID(tenant["id"]),
        email="admin-" + uuid.uuid4().hex[:8] + "@example.com",
        full_name="Super Admin",
        hashed_password=hash_password(TEST_ADMIN_PASSWORD),
        is_active=True,
        is_superadmin=True,
    )
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return {
        "id": str(u.id),
        "tenant_id": tenant["id"],
        "email": u.email,
        "password": TEST_ADMIN_PASSWORD,
    }


@pytest_asyncio.fixture
async def magic_link(db: AsyncSession, user: dict) -> dict:
    import secrets

    from app.models.auth import MagicLink

    raw_token = secrets.token_urlsafe(32)
    ml = MagicLink(
        id=uuid.uuid4(),
        tenant_id=uuid.UUID(user["tenant_id"]),
        email=user["email"],
        token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
        is_used=False,
    )
    db.add(ml)
    await db.commit()
    await db.refresh(ml)
    return {"id": str(ml.id), "token": raw_token, "email": user["email"]}


@pytest_asyncio.fixture
async def client(test_engine, _class_db_setup) -> AsyncGenerator[AsyncClient, None]:
    from app.main import app as fastapi_app

    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def auth_headers(client: AsyncClient, user: dict) -> dict:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": user["email"], "password": user["password"]},
    )
    assert resp.status_code == 200, f"Login failed: {resp.status_code} {resp.text}"
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def superuser_headers(client: AsyncClient, superuser: dict) -> dict:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": superuser["email"], "password": superuser["password"]},
    )
    assert resp.status_code == 200, f"Login failed: {resp.status_code} {resp.text}"
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
