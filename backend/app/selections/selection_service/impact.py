"""Who a company's opt-ins reach: per-jurisdiction user counts, and the users a
change would take an opt-in from."""

import uuid
from collections.abc import Iterable

from sqlmodel import Session, col, func, select

from app.selections.selection_models import (
    JurisdictionAffectedUser,
    JurisdictionAffectedUsers,
    SelectionChange,
    SelectionPreview,
    UserJurisdiction,
)
from app.selections.selection_service.owner import SelectionOwner
from app.selections.selection_service.selection_reading import (
    in_display_order,
    selected_ids,
)
from app.selections.selection_service.versions import get_selection_version
from app.selections.selection_service.writing import resolve_change, validate_selectable
from app.users.user_models import User


def get_company_jurisdiction_user_counts(
    *, session: Session, company_id: uuid.UUID
) -> list[tuple[uuid.UUID, int]]:
    """Users per jurisdiction within the company; jurisdictions with none are omitted."""
    statement = (
        select(UserJurisdiction.jurisdiction_id, func.count())
        .where(UserJurisdiction.company_id == company_id)
        .group_by(col(UserJurisdiction.jurisdiction_id))
    )
    return [(j, n) for j, n in session.exec(statement).all()]


def get_company_jurisdiction_affected_users(
    *, session: Session, company_id: uuid.UUID, jurisdiction_ids: Iterable[uuid.UUID]
) -> list[tuple[User, int]]:
    """Company users who selected any of the ids, with how many of them each selected."""
    ids = set(jurisdiction_ids)
    if not ids:
        return []
    statement = (
        select(User, func.count())
        .join(UserJurisdiction, col(UserJurisdiction.user_id) == User.id)
        .where(
            UserJurisdiction.company_id == company_id,
            col(UserJurisdiction.jurisdiction_id).in_(ids),
        )
        .group_by(col(User.id))
        .order_by(
            func.lower(func.coalesce(User.full_name, User.email)), col(User.email)
        )
    )
    return [(u, n) for u, n in session.exec(statement).all()]


def preview_company_change(
    *, session: Session, company_id: uuid.UUID, change: SelectionChange
) -> SelectionPreview:
    """What apply_change would do to the company's opt-ins, and who'd lose one.
    Nothing is written."""
    owner = SelectionOwner.of_company(company_id)
    version = get_selection_version(session=session, owner=owner)
    current = selected_ids(session=session, owner=owner)
    wanted = resolve_change(session=session, owner=owner, change=change)
    added, removed = wanted - current, current - wanted
    validate_selectable(session=session, ids=added)
    rows = get_company_jurisdiction_affected_users(
        session=session, company_id=company_id, jurisdiction_ids=removed
    )
    return SelectionPreview(
        version=version,
        added=in_display_order(session=session, ids=added),
        removed=in_display_order(session=session, ids=removed),
        affected_users=JurisdictionAffectedUsers(
            data=[
                JurisdictionAffectedUser(
                    id=u.id, email=u.email, full_name=u.full_name, jurisdiction_count=n
                )
                for u, n in rows
            ],
            count=len(rows),
        ),
    )
