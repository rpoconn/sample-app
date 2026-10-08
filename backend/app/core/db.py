import json
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import event
from sqlmodel import Session, create_engine, select

from app import crud
from app.core.config import settings
from app.models import DEFAULT_COMPANY_ID, CompanyRole, User, UserCreate

JURISDICTIONS_SEED_FILE = Path(__file__).parents[1] / "data" / "jurisdictions.json"

# Sample plan from the PRD: US national, every state except Wyoming and Utah,
# San Francisco as the only city, and all of Canada
PLAN_EXCLUDED_STATES = {"Wyoming", "Utah"}
PLAN_CITIES = {"San Francisco"}

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


def _plan_jurisdiction_ids(nodes: list[dict[str, Any]]) -> list[uuid.UUID]:
    """Selectable ids in the seed tree that fall within the sample plan."""
    ids: list[uuid.UUID] = []

    def in_plan(names: list[str], node: dict[str, Any]) -> bool:
        if names[0] == "Canada":
            return True
        if names[0] != "United States" or len(names) < 2:
            return False
        if names[1] == "National":
            return True
        if names[1] != "States" or len(names) < 3:
            return False
        if names[2] in PLAN_EXCLUDED_STATES:
            return False
        return node.get("regionType") != "city" or node["name"] in PLAN_CITIES

    def walk(children: list[dict[str, Any]], names: list[str]) -> None:
        for node in children:
            path = [*names, node["name"]]
            if not node.get("isStructural", False) and in_plan(path, node):
                ids.append(uuid.UUID(node["id"]))
            walk(node.get("jurisdictions", []), path)

    walk(nodes, [])
    return ids


def init_db(session: Session) -> None:
    # Tables should be created with Alembic migrations
    # But if you don't want to use migrations, create
    # the tables un-commenting the next lines
    # from sqlmodel import SQLModel

    # This works because the models are already imported and registered from app.models
    # SQLModel.metadata.create_all(engine)

    # Normally created by the migration; recreated here if it was removed
    crud.ensure_default_company(session=session, name="[Company Name]")

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
        crud.apply_selection(
            session=session,
            owner=crud.SelectionOwner.of_company(DEFAULT_COMPANY_ID),
            wanted=_plan_jurisdiction_ids(nodes),
            expected_version=None,
        )
