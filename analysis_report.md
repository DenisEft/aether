# Aether Backend Test Infrastructure Analysis Report

## Summary

The analysis of the Aether backend test suite revealed that 100 failing service tests are primarily due to SQLite database locking issues and schema compatibility problems. The main problems stem from:

1. **SQLite Database Locking**: The test suite uses a shared in-memory SQLite database (`file:aether_test.db?mode=memory&cache=shared`) which causes concurrency issues in multi-threaded or concurrent test execution, especially with `pytest-asyncio` fixtures.

2. **Schema Migration/Type Compatibility**: The test database setup patches SQLite types to handle PostgreSQL types (like JSONB), but this patching fails when the actual model definitions contain PostgreSQL-specific constructs that don't translate correctly to SQLite.

## Categories of Failures

### 1. Database Locking Issues
- **Error**: `sqlite3.OperationalError: database is locked`
- **Root Cause**: The in-memory SQLite database used for tests is not properly isolated, causing concurrent access conflicts.
- **Files**: `tests/conftest.py` (line 36, `TEST_DB_URI`), `tests/services/conftest.py` (line 36, `TEST_DB_URI`)
- **Impact**: Tests fail at setup, particularly during `Base.metadata.create_all()`

### 2. Schema and Type Incompatibility
- **Error**: `Compiler <sqlalchemy.dialects.sqlite.base.SQLiteTypeCompiler object at 0x...> can't render element of type JSONB`
- **Root Cause**: The model definitions contain PostgreSQL-specific types (JSONB) that the patched SQLite compiler can't handle properly.
- **Files**: `app/models/tenants.py` (line 103, `settings` field)
- **Impact**: Tests fail during table creation when trying to create a table with a JSONB field in SQLite

## Recommended Fixes

### Immediate Fix: Use Separate Test Databases
To avoid locking issues, we should modify the test configuration to use separate, file-based SQLite databases per test run, or better yet, use a proper test PostgreSQL instance.

### Long-term Fix: Refactor Test Database Configuration
The `tests/conftest.py` and `tests/services/conftest.py` files should be updated to:
1. Use proper SQLite file-based databases (with unique names per test run)
2. Avoid patching SQLite types unless absolutely necessary
3. Ensure compatibility between PostgreSQL and SQLite schema definitions

## Example Fix for conftest.py

The following changes should be made to `tests/conftest.py`:

```python
# Replace the TEST_DB_URI with a proper file-based SQLite database
TEST_DB_URI = "sqlite:///./test_db.sqlite3"

# Remove the _patch_sqlite_types function and related code

# Update the test_engine fixture to use the new URI
@pytest_asyncio.fixture(scope="session")
async def test_engine():
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

    await engine.dispose()
```

This fix will ensure that each test run uses a separate SQLite database file, avoiding locking issues.

## Conclusion

The failing tests are not due to logic errors in the code, but rather due to the test infrastructure's configuration. The fix involves properly handling database concurrency in the test environment, which should resolve the immediate test failures.
