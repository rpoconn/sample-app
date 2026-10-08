from typing import Any

from sqlalchemy import event
from sqlmodel import create_engine

from app.core.config import settings

engine = create_engine(settings.DATABASE_URL, connect_args={"check_same_thread": False})


# SQLite ignores foreign keys (and ON DELETE CASCADE) unless enabled per connection
@event.listens_for(engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection: Any, _connection_record: Any) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()
