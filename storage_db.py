import os
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, Optional

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    event,
    inspect,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import DBAPIError

DEFAULT_DB_PATH = Path("~/.xmcp/xmcp.db").expanduser()
SQLITE_BUSY_TIMEOUT_MS = int(os.getenv("SQLITE_BUSY_TIMEOUT_MS", "5000"))

# Literal SQL defaults for backfilling NOT NULL columns onto existing rows.
# A NOT NULL column added without one cannot be applied to a populated table,
# so a missing entry here is a programming error rather than a default.
_BACKFILL_DEFAULTS = {"blocks": "'[]'", "schema_version": "''", "dispatched_action": "''"}

# Bounded, because losing the create race is expected and transient: the retry
# only has to outlast another process committing its CREATE TABLE.
_SCHEMA_CREATE_ATTEMPTS = 3
_SCHEMA_RETRY_DELAY_S = 0.25

_ENGINE: Optional[Engine] = None
_ENGINE_LOCK = threading.Lock()

metadata = MetaData()

json_type = JSON().with_variant(JSONB, "postgresql")

timeline_items = Table(
    "timeline_items",
    metadata,
    Column("id", String, primary_key=True),
    Column("user_id", String, nullable=False, index=True),
    Column("title", String, nullable=False),
    Column("body", Text, nullable=False, default=""),
    # Typed card content. `body` stays the authoritative text form -- it is
    # derived from these blocks when a caller doesn't supply one -- so a reader
    # that predates typed cards keeps working.
    Column("blocks", json_type, nullable=False, default=list),
    Column("schema_version", String, nullable=False, default=""),
    # The action this card has already dispatched, or "" while unclaimed. A
    # conditional UPDATE against this column is what makes approval
    # single-shot; see timeline_store.claim_action.
    Column("dispatched_action", String, nullable=False, default=""),
    Column("status", String, nullable=False, index=True),
    Column("posted_by", String, nullable=False),
    Column("actions", json_type, nullable=False),
    Column("metadata", json_type, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, index=True),
    Column("updated_at", DateTime(timezone=True), nullable=True, index=True),
)

a2a_agents = Table(
    "a2a_agents",
    metadata,
    Column("id", String, primary_key=True),
    Column("name", String, nullable=False),
    Column("description", Text, nullable=False, default=""),
    Column("status", String, nullable=False, default="offline"),
    Column("endpoint", String, nullable=False, default=""),
    Column("kind", String, nullable=False, default="agent"),
    Column("tags", json_type, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, index=True),
)

a2a_messages = Table(
    "a2a_messages",
    metadata,
    Column("id", String, primary_key=True),
    Column("from_agent", String, nullable=False),
    Column("to_agent", String, nullable=False, index=True),
    Column("type", String, nullable=False),
    Column("content", Text, nullable=False, default=""),
    Column("metadata", json_type, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, index=True),
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def normalize_database_url(url: Optional[str]) -> str:
    raw = (url or "").strip()
    if not raw:
        return f"sqlite:///{DEFAULT_DB_PATH}"
    # Railway injects the legacy postgres:// scheme, which SQLAlchemy rejects.
    # Both postgres:// and a bare postgresql:// also resolve to the psycopg2
    # driver, which we do not ship -- requirements.txt pins psycopg 3. Pin the
    # driver explicitly so the Postgres path does not fail on first connect.
    # An explicit postgresql+<driver>:// is left alone.
    for prefix in ("postgres://", "postgresql://"):
        if raw.startswith(prefix):
            return "postgresql+psycopg://" + raw[len(prefix) :]
    if raw.startswith("sqlite:///"):
        path = raw[len("sqlite:///") :]
        if path.startswith("~"):
            return f"sqlite:///{Path(path).expanduser()}"
    return raw


def get_database_url() -> str:
    return normalize_database_url(os.getenv("DATABASE_URL"))


def _configure_sqlite(engine: Engine) -> None:
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragmas(dbapi_connection, _connection_record) -> None:  # type: ignore[no-untyped-def]
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute(f"PRAGMA busy_timeout={SQLITE_BUSY_TIMEOUT_MS}")
        cursor.close()


def _is_duplicate_column(exc: DBAPIError) -> bool:
    """Whether a failed ADD COLUMN failed only because the column is there.

    Matched on message text rather than a driver error code, because the two
    backends raise unrelated exception types (psycopg's DuplicateColumn vs
    SQLite's generic OperationalError). Anything that is not recognisably a
    duplicate column is re-raised -- a genuinely broken migration must not be
    swallowed here.
    """
    message = str(getattr(exc, "orig", exc)).lower()
    return "already exists" in message or "duplicate column" in message


def _add_missing_columns(engine: Engine) -> None:
    """Add columns that `create_all` won't.

    `metadata.create_all` creates missing *tables* and then leaves an existing
    table alone, so a database created by an earlier revision keeps its old
    column set and every query naming a newer column fails. There is no
    migration framework here, so bring the one table that has gained columns
    up to date in place. Each ADD COLUMN is guarded by a live reflection, which
    makes this a no-op on an already-current database.

    The reflection is not a lock, though. All four services boot at once and
    share one database, so several can reflect "missing" before any of them
    alters, and the losers of that race would otherwise crash on startup with
    a duplicate-column error. Each statement therefore runs in its own
    transaction (an error poisons the whole transaction on Postgres, which
    would strand any column after the first) and treats "already exists" as
    success -- another process adding the column is the desired end state.
    """
    inspector = inspect(engine)
    if not inspector.has_table(timeline_items.name):
        return

    existing = {column["name"] for column in inspector.get_columns(timeline_items.name)}
    missing = [c for c in timeline_items.columns if c.name not in existing]
    if not missing:
        return

    type_compiler = engine.dialect.type_compiler_instance
    preparer = engine.dialect.identifier_preparer
    for column in missing:
        # Read the intent off the Column rather than hardcoding it. Every
        # column added so far happens to be String/JSON and NOT NULL, and a
        # blanket "NOT NULL DEFAULT ''" works only for those: a DateTime would
        # be rejected by Postgres and silently store garbage in SQLite, and a
        # nullable column would be forced NOT NULL against its own definition.
        # This path exists for legacy databases, so that lands on startup in
        # production rather than in a fresh test database.
        constraint = ""
        if not column.nullable:
            default = _BACKFILL_DEFAULTS.get(column.name)
            if default is None:
                raise RuntimeError(
                    f"{timeline_items.name}.{column.name} is NOT NULL with no backfill "
                    "default; existing rows need one -- add it to _BACKFILL_DEFAULTS"
                )
            constraint = f" NOT NULL DEFAULT {default}"
        statement = text(
            f"ALTER TABLE {preparer.format_table(timeline_items)} "
            f"ADD COLUMN {preparer.quote(column.name)} "
            f"{type_compiler.process(column.type)}{constraint}"
        )
        try:
            with engine.begin() as conn:
                conn.execute(statement)
        except DBAPIError as exc:
            if not _is_duplicate_column(exc):
                raise


def _create_tables(engine: Engine) -> None:
    """Create the schema, tolerating another service creating it concurrently.

    `create_all` checks which tables exist and then creates the rest, which is
    the same reflect-then-write race as `_add_missing_columns` -- and it bites
    harder, because it happens on the *first* deploy against an empty database
    with every service booting at once. Postgres fails the loser with a unique
    violation on its own catalog rather than anything table-specific, so the
    resolution is to ask whether the schema is there now: if it is, whoever
    created it did the job.
    """
    expected = set(metadata.tables)
    for attempt in range(_SCHEMA_CREATE_ATTEMPTS):
        try:
            metadata.create_all(engine)
            return
        except DBAPIError:
            # Reflect fresh -- the winner may still have been committing.
            if expected <= set(inspect(engine).get_table_names()):
                return
            if attempt == _SCHEMA_CREATE_ATTEMPTS - 1:
                raise
            time.sleep(_SCHEMA_RETRY_DELAY_S * (attempt + 1))


def _create_engine() -> Engine:
    database_url = get_database_url()
    connect_args: Dict[str, Any] = {}
    if database_url.startswith("sqlite://"):
        connect_args = {"check_same_thread": False}
    engine = create_engine(database_url, future=True, pool_pre_ping=True, connect_args=connect_args)
    if database_url.startswith("sqlite://"):
        _configure_sqlite(engine)
    _create_tables(engine)
    _add_missing_columns(engine)
    return engine


def get_engine() -> Engine:
    global _ENGINE
    if _ENGINE is not None:
        return _ENGINE
    with _ENGINE_LOCK:
        if _ENGINE is None:
            _ENGINE = _create_engine()
    return _ENGINE


@contextmanager
def write_connection() -> Iterator[Connection]:
    engine = get_engine()
    conn = engine.connect()
    if engine.dialect.name == "sqlite":
        conn.exec_driver_sql("BEGIN IMMEDIATE")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        return

    trans = conn.begin()
    try:
        yield conn
        trans.commit()
    except Exception:
        trans.rollback()
        raise
    finally:
        conn.close()


@contextmanager
def read_connection() -> Iterator[Connection]:
    conn = get_engine().connect()
    try:
        yield conn
    finally:
        conn.close()


def row_to_dict(row: Any) -> Dict[str, Any]:
    return dict(row._mapping)


def serialize_record(record: Dict[str, Any]) -> Dict[str, Any]:
    value = dict(record)
    for field in ("created_at", "updated_at"):
        timestamp = value.get(field)
        if isinstance(timestamp, datetime):
            value[field] = timestamp.isoformat()
    return value


def merge_json(current: Any, update: Dict[str, Any]) -> Dict[str, Any]:
    base = current if isinstance(current, dict) else {}
    return {**base, **update}


def ensure_sqlite_health() -> None:
    if get_engine().dialect.name != "sqlite":
        return
    with read_connection() as conn:
        conn.execute(text("SELECT 1"))


def reset_engine_for_tests() -> None:
    global _ENGINE
    with _ENGINE_LOCK:
        if _ENGINE is not None:
            _ENGINE.dispose()
        _ENGINE = None
