from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def normalize_database_url(url: str | URL) -> URL:
    parsed = make_url(url)
    driver = parsed.drivername
    if driver in {"postgres", "postgresql"}:
        parsed = parsed.set(drivername="postgresql+psycopg")
    backend = parsed.get_backend_name()
    if backend not in {"sqlite", "postgresql"}:
        raise ValueError("Only SQLite and PostgreSQL databases are supported")
    return parsed


class Database:
    def __init__(self, url: str | URL):
        parsed = normalize_database_url(url)
        options = {"hide_parameters": True, "pool_pre_ping": True, "echo": False}
        if parsed.get_backend_name() == "sqlite":
            options["connect_args"] = {"check_same_thread": False, "timeout": 5}
            if parsed.database in {None, "", ":memory:"}:
                options["poolclass"] = StaticPool
            else:
                path = Path(parsed.database)
                path = path if path.is_absolute() else BACKEND_ROOT / path
                path.parent.mkdir(parents=True, exist_ok=True)
                parsed = parsed.set(database=str(path.resolve()))
        elif parsed.get_backend_name() == "postgresql":
            options.setdefault("pool_size", 10)
            options.setdefault("max_overflow", 20)
            options.setdefault("pool_recycle", 300)
            options.setdefault("pool_timeout", 30)
        self.engine = create_engine(parsed, **options)
        if parsed.get_backend_name() == "sqlite":

            @event.listens_for(self.engine, "connect")
            def sqlite_settings(connection, record):
                cursor = connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()

        self.sessions = sessionmaker(self.engine, expire_on_commit=False)

    def check_connection(self) -> dict:
        with self.engine.connect() as connection:
            result = connection.execute(text("SELECT 1")).scalar()
            return {
                "connected": result == 1,
                "backend": self.engine.dialect.name,
                "driver": self.engine.dialect.driver,
            }

    def dispose(self):
        self.engine.dispose()

