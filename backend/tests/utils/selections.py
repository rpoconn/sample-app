import uuid
from collections.abc import Iterable

from sqlmodel import Session

from app.selections.selection_models import JurisdictionSelectionOut
from app.selections.selection_service import SelectionOwner, apply_selection
from app.users.user_models import User


def set_company_ids(
    db: Session, company_id: uuid.UUID, ids: Iterable[uuid.UUID]
) -> JurisdictionSelectionOut:
    """Replace a company's opt-ins, whatever version they're at."""
    return apply_selection(
        session=db,
        owner=SelectionOwner.of_company(company_id),
        wanted=ids,
        expected_version=None,
    )


def set_user_ids(
    db: Session, user: User, ids: Iterable[uuid.UUID]
) -> JurisdictionSelectionOut:
    """Replace a user's opt-ins, whatever version they're at."""
    return apply_selection(
        session=db,
        owner=SelectionOwner.of_user(user),
        wanted=ids,
        expected_version=None,
    )
