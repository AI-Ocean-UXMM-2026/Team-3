from alembic import command
from alembic.config import Config

from app.db.session import BACKEND_ROOT, Database


def upgrade_database(database: Database):
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    with database.engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
