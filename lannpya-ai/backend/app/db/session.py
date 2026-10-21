from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Database:
    def __init__(self, url: str):
        parsed = make_url(url)
        if parsed.get_backend_name() not in {"sqlite", "postgresql"}:
            raise ValueError("Only SQLite and PostgreSQL databases are supported")
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
        self.engine = create_engine(parsed, **options)
        if parsed.get_backend_name() == "sqlite":

            @event.listens_for(self.engine, "connect")
            def sqlite_settings(connection, record):
                cursor = connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()

        self.sessions = sessionmaker(self.engine, expire_on_commit=False)

    def dispose(self):
        self.engine.dispose()
