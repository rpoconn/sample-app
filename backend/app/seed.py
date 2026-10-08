import json
import uuid
from pathlib import Path
from typing import Any

from sqlmodel import Session

from app.companies import company_service as companies
from app.companies.company_models import DEFAULT_COMPANY_ID, CompanyRole
from app.core.config import settings
from app.jurisdictions import jurisdiction_service as jurisdictions
from app.selections import selection_service as selections
from app.users import user_service as users
from app.users.user_models import UserCreate

JURISDICTIONS_SEED_FILE = Path(__file__).parent / "data" / "jurisdictions.json"

# Sample plan from the PRD: US national, every state except Wyoming and Utah,
# San Francisco as the only city, and all of Canada
PLAN_EXCLUDED_STATES = {"Wyoming", "Utah"}
PLAN_CITIES = {"San Francisco"}


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
    # Tables are created by Alembic migrations; app.tables registers every model
    # Normally created by the migration; recreated here if it was removed
    companies.ensure_default_company(session=session, name="[Company Name]")

    user = users.get_user_by_email(session=session, email=settings.FIRST_SUPERUSER)
    if not user:
        user_in = UserCreate(
            email=settings.FIRST_SUPERUSER,
            password=settings.FIRST_SUPERUSER_PASSWORD,
            is_superuser=True,
            company_role=CompanyRole.admin,
        )
        user = users.create_user(session=session, user_create=user_in)

        # Seed only on first setup, so later edits to jurisdictions are not undone
        nodes = json.loads(JURISDICTIONS_SEED_FILE.read_text(encoding="utf-8"))
        jurisdictions.seed_jurisdictions(session=session, nodes=nodes)
        selections.apply_selection(
            session=session,
            owner=selections.SelectionOwner.of_company(DEFAULT_COMPANY_ID),
            wanted=_plan_jurisdiction_ids(nodes),
            expected_version=None,
        )
