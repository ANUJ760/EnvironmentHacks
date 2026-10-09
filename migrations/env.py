from alembic import context
from sqlalchemy import create_engine

from ecotwin.config import get_settings
from ecotwin.db import models  # noqa: F401
from ecotwin.db.base import Base


def include_name(name, type_, parent_names):
    if type_ == "table":
        return name in Base.metadata.tables
    if type_ == "schema":
        return name is None
    return True


url = get_settings().database_url.get_secret_value()
if context.is_offline_mode():
    context.configure(url=url, target_metadata=Base.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    with create_engine(url).connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=Base.metadata,
            compare_type=True,
            include_name=include_name,
        )
        with context.begin_transaction():
            context.run_migrations()
