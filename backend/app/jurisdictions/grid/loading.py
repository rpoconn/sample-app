"""Database reads that feed the grid: a sorted tree, and the scope's opt-ins."""

from typing import Any

from sqlmodel import Session, case, col, func, select

from app.jurisdictions.grid.grid_models import SortDir, TreeSortBy
from app.jurisdictions.grid.query import Selection
from app.jurisdictions.jurisdiction_models import Jurisdiction
from app.jurisdictions.jurisdiction_service.jurisdiction_reading import CANONICAL_ORDER
from app.selections.selection_models import (
    CompanyJurisdiction,
    SelectionScope,
    UserJurisdiction,
)
from app.selections.selection_service.owner import SelectionOwner
from app.selections.selection_service.selection_reading import selected_ids
from app.users.user_models import User


def get_jurisdiction_tree(
    *,
    session: Session,
    user: User,
    sort_by: TreeSortBy | None = None,
    sort_dir: SortDir = "asc",
    scope: SelectionScope = "company",
) -> list[Jurisdiction]:
    """Every jurisdiction, flat. Only sibling order matters; the client nests by parent_id."""
    statement = select(Jurisdiction)
    name_key = func.lower(Jurisdiction.name)
    if sort_by is None:
        order: list[Any] = CANONICAL_ORDER
    elif sort_by == "name":
        key = name_key.desc() if sort_dir == "desc" else name_key.asc()
        order = [key, col(Jurisdiction.sort_order)]
    else:
        if scope == "company":
            link_id = col(CompanyJurisdiction.jurisdiction_id)
            statement = statement.outerjoin(
                CompanyJurisdiction,
                (link_id == Jurisdiction.id)
                & (col(CompanyJurisdiction.company_id) == user.company_id),
            )
        else:
            link_id = col(UserJurisdiction.jurisdiction_id)
            statement = statement.outerjoin(
                UserJurisdiction,
                (link_id == Jurisdiction.id)
                & (col(UserJurisdiction.user_id) == user.id),
            )
        # Structural nodes can't be selected, so they never count as enabled
        enabled = case(
            (link_id.is_not(None) & ~col(Jurisdiction.is_structural), 1), else_=0
        )
        key = enabled.desc() if sort_dir == "desc" else enabled.asc()
        order = [key, name_key, col(Jurisdiction.sort_order)]
    return list(session.exec(statement.order_by(*order)).all())


def get_jurisdiction_selection(
    *, session: Session, user: User, scope: SelectionScope
) -> Selection:
    """The company's opt-ins, and those on in the scope shown."""
    licensed = frozenset(
        selected_ids(session=session, owner=SelectionOwner.of_company(user.company_id))
    )
    enabled = (
        licensed
        if scope == "company"
        else frozenset(
            selected_ids(session=session, owner=SelectionOwner.of_user(user))
        )
    )
    return Selection(scope=scope, enabled_ids=enabled, licensed_ids=licensed)
