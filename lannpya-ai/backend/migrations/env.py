from alembic import context

from app.core.config import Settings
from app.db import (
    buyer_models,  # noqa: F401
    rider_models,  # noqa: F401
    workflow_models,  # noqa: F401
)
from app.db.models import Base
from app.db.session import Database

config = context.config
target_metadata = Base.metadata


def database_url():
    return config.attributes.get("database_url") or Settings().database_url.get_secret_value()


if context.is_offline_mode():
    context.configure(
        url=database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    supplied = config.attributes.get("connection")
    if supplied is not None:
        context.configure(
            connection=supplied,
            target_metadata=target_metadata,
            compare_type=True,
            render_as_batch=supplied.dialect.name == "sqlite",
        )
        with context.begin_transaction():
            context.run_migrations()
    else:
        database = Database(database_url())
        try:
            with database.engine.connect() as connection:
                context.configure(
                    connection=connection,
                    target_metadata=target_metadata,
                    compare_type=True,
                    render_as_batch=connection.dialect.name == "sqlite",
                )
                with context.begin_transaction():
                    context.run_migrations()
        finally:
            database.dispose()
