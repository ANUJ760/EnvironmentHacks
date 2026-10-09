from functools import lru_cache
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from ecotwin.config import get_settings

@lru_cache
def session_factory() -> sessionmaker[Session]:
    settings = get_settings()
    engine = create_engine(settings.database_url.get_secret_value(), pool_pre_ping=True,
        pool_size=settings.db_pool_size,max_overflow=settings.db_max_overflow,
        connect_args={"options": "-c statement_timeout=30000 -c lock_timeout=5000"})
    return sessionmaker(engine, expire_on_commit=False)

def session_dependency():
    with session_factory()() as session:
        yield session
