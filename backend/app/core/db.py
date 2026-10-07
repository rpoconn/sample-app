import json
from pathlib import Path
from typing import Any

from sqlalchemy import event
from sqlmodel import Session, create_engine, select

from app import crud
from app.core.config import settings
from app.models import CompanyRole, User, UserCreate

JURISDICTIONS_SEED_FILE = Path(__file__).parents[1] / "data" / "jurisdictions.json"

engine = create_engine(settings.DATABASE_URL, connect_args={"check_same_thread": False})


# SQLite ignores foreign keys (and ON DELETE CASCADE) unless enabled per connection
@event.listens_for(engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection: Any, _connection_record: Any) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


# make sure all SQLModel models are imported (app.models) before initializing DB
# otherwise, SQLModel might fail to initialize relationships properly
# for more details: https://github.com/fastapi/full-stack-fastapi-template/issues/28


def init_db(session: Session) -> None:
    # Tables should be created with Alembic migrations
    # But if you don't want to use migrations, create
    # the tables un-commenting the next lines
    # from sqlmodel import SQLModel

    # This works because the models are already imported and registered from app.models
    # SQLModel.metadata.create_all(engine)

    # Normally created by the migration; recreated here if it was removed
    crud.ensure_default_company(session=session, name="Default")

    user = session.exec(
        select(User).where(User.email == settings.FIRST_SUPERUSER)
    ).first()
    if not user:
        user_in = UserCreate(
            email=settings.FIRST_SUPERUSER,
            password=settings.FIRST_SUPERUSER_PASSWORD,
            is_superuser=True,
            company_role=CompanyRole.admin,
        )
        user = crud.create_user(session=session, user_create=user_in)

        # Seed only on first setup, so later edits to jurisdictions are not undone
        nodes = json.loads(JURISDICTIONS_SEED_FILE.read_text(encoding="utf-8"))
        crud.seed_jurisdictions(session=session, nodes=nodes)
