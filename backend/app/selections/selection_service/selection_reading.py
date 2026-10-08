import uuid

from sqlmodel import Session, col, select

from app.jurisdictions.jurisdiction_models import Jurisdiction
from app.selections.selection_models import (
    CompanyJurisdiction,
    JurisdictionSelectionOut,
    UserJurisdiction,
)
from app.selections.selection_service.owner import SelectionOwner
from app.selections.selection_service.versions import get_selection_version


def selected_ids(*, session: Session, owner: SelectionOwner) -> set[uuid.UUID]:
    if owner.kind == "company":
        statement = select(CompanyJurisdiction.jurisdiction_id).where(
            CompanyJurisdiction.company_id == owner.id
        )
    else:
        statement = select(UserJurisdiction.jurisdiction_id).where(
            UserJurisdiction.user_id == owner.id
        )
    return set(session.exec(statement).all())


def in_display_order(*, session: Session, ids: set[uuid.UUID]) -> list[uuid.UUID]:
    if not ids:
        return []
    statement = (
        select(Jurisdiction.id)
        .where(col(Jurisdiction.id).in_(ids))
        .order_by(col(Jurisdiction.name_path))
    )
    return list(session.exec(statement).all())


def get_selection(
    *, session: Session, owner: SelectionOwner
) -> JurisdictionSelectionOut:
    """The owner's opt-ins, ordered by name path, and the version they're at."""
    version = get_selection_version(session=session, owner=owner)
    ids = in_display_order(
        session=session, ids=selected_ids(session=session, owner=owner)
    )
    return JurisdictionSelectionOut(
        jurisdiction_ids=ids, count=len(ids), version=version
    )
