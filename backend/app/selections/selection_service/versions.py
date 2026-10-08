"""Selection versions: the ETag of an owner's opt-ins, bumped on every write to them."""

import uuid
from collections.abc import Iterable
from typing import Any

from sqlalchemy import update
from sqlmodel import Session, col, select

from app.companies.company_models import Company
from app.core.errors import NotFound, PreconditionFailed
from app.selections.selection_service.owner import SelectionOwner, owner_table
from app.users.user_models import User


def get_selection_version(*, session: Session, owner: SelectionOwner) -> int:
    table = owner_table(owner)
    version = session.exec(
        select(table.jurisdictions_version).where(table.id == owner.id)
    ).first()
    if version is None:
        raise NotFound(
            f"{owner.kind.capitalize()} not found", code=f"{owner.kind}_not_found"
        )
    return version


def bump_version(
    *, session: Session, owner: SelectionOwner, expected: int | None
) -> None:
    """Compare-and-swap the owner's version inside the write transaction, so of two
    writes from the same snapshot only the first lands. None bumps unconditionally.
    The UPDATE also takes SQLite's write lock before the current ids are read."""
    table = owner_table(owner)
    statement = (
        update(table)
        .where(col(table.id) == owner.id)
        .values(jurisdictions_version=table.jurisdictions_version + 1)
    )
    if expected is not None:
        statement = statement.where(col(table.jurisdictions_version) == expected)
    result = session.exec(statement)
    if result.rowcount != 1:
        session.rollback()
        current = get_selection_version(session=session, owner=owner)
        raise PreconditionFailed(
            "The selection changed since you loaded it",
            context={"version": current},
        )


def bump_user_versions(*, session: Session, user_ids: Any) -> None:
    session.exec(
        update(User)
        .where(col(User.id).in_(user_ids))
        .values(jurisdictions_version=User.jurisdictions_version + 1)
    )


def bump_company_versions(
    *, session: Session, company_ids: Iterable[uuid.UUID]
) -> None:
    session.exec(
        update(Company)
        .where(col(Company.id).in_(company_ids))
        .values(jurisdictions_version=Company.jurisdictions_version + 1)
    )
