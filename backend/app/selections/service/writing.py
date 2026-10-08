import uuid
from collections.abc import Iterable

from sqlmodel import Session, col, delete, select

from app.core.errors import InvalidInput
from app.jurisdictions.models import Jurisdiction
from app.jurisdictions.service.reading import get_subtree_ids
from app.selections.models import (
    CompanyJurisdiction,
    JurisdictionSelectionOut,
    SelectionChange,
    UserJurisdiction,
)
from app.selections.service.owner import SelectionOwner
from app.selections.service.reading import get_selection, selected_ids
from app.selections.service.versions import bump_user_versions, bump_version


def validate_selectable(*, session: Session, ids: set[uuid.UUID]) -> None:
    if not ids:
        return
    rows = session.exec(select(Jurisdiction).where(col(Jurisdiction.id).in_(ids))).all()
    missing = ids - {j.id for j in rows}
    if missing:
        raise InvalidInput(
            "Unknown jurisdiction ids",
            code="unknown_jurisdiction",
            context={"jurisdiction_ids": sorted(str(i) for i in missing)},
        )
    structural = [j for j in rows if j.is_structural]
    if structural:
        raise InvalidInput(
            "Structural jurisdictions cannot be selected",
            code="jurisdiction_structural",
            context={
                "jurisdiction_ids": sorted(str(j.id) for j in structural),
                "name_paths": sorted(j.name_path for j in structural),
            },
        )


def _write_selection(
    *, session: Session, owner: SelectionOwner, wanted: set[uuid.UUID]
) -> None:
    validate_selectable(session=session, ids=wanted)
    if owner.kind == "user":
        licensed = selected_ids(
            session=session, owner=SelectionOwner.of_company(owner.company_id)
        )
        if outside := wanted - licensed:
            raise InvalidInput(
                "The company has not opted into these jurisdictions",
                code="jurisdiction_not_licensed",
                context={"jurisdiction_ids": sorted(str(i) for i in outside)},
            )
    current = selected_ids(session=session, owner=owner)
    removed, added = current - wanted, wanted - current
    if owner.kind == "company":
        if removed:
            # The FK cascade drops users' opt-ins without touching their versions
            bump_user_versions(
                session=session,
                user_ids=select(UserJurisdiction.user_id).where(
                    col(UserJurisdiction.company_id) == owner.id,
                    col(UserJurisdiction.jurisdiction_id).in_(removed),
                ),
            )
            session.exec(
                delete(CompanyJurisdiction).where(
                    col(CompanyJurisdiction.company_id) == owner.id,
                    col(CompanyJurisdiction.jurisdiction_id).in_(removed),
                )
            )
        for jurisdiction_id in added:
            session.add(
                CompanyJurisdiction(
                    company_id=owner.id, jurisdiction_id=jurisdiction_id
                )
            )
        return
    if removed:
        session.exec(
            delete(UserJurisdiction).where(
                col(UserJurisdiction.user_id) == owner.id,
                col(UserJurisdiction.jurisdiction_id).in_(removed),
            )
        )
    for jurisdiction_id in added:
        session.add(
            UserJurisdiction(
                user_id=owner.id,
                company_id=owner.company_id,
                jurisdiction_id=jurisdiction_id,
            )
        )


def apply_selection(
    *,
    session: Session,
    owner: SelectionOwner,
    wanted: Iterable[uuid.UUID],
    expected_version: int | None,
) -> JurisdictionSelectionOut:
    """Replace the owner's opt-ins with `wanted`. A company's removed ids cascade to
    its users' opt-ins and bump those users' versions."""
    try:
        bump_version(session=session, owner=owner, expected=expected_version)
        _write_selection(session=session, owner=owner, wanted=set(wanted))
    except Exception:
        session.rollback()
        raise
    session.commit()
    return get_selection(session=session, owner=owner)


def resolve_change(
    *, session: Session, owner: SelectionOwner, change: SelectionChange
) -> set[uuid.UUID]:
    """The opt-ins after the change: current, plus adds, minus removes. A user's
    add_subtrees skips what the company hasn't licensed; an explicit add doesn't."""
    pairs = [
        (change.add, change.remove),
        (change.add_subtrees, change.remove_subtrees),
    ]
    for add, remove in pairs:
        if both := set(add) & set(remove):
            raise InvalidInput(
                "Ids can't be both added and removed",
                code="selection_conflict",
                context={"jurisdiction_ids": sorted(str(i) for i in both)},
            )
    add_subtrees = get_subtree_ids(session=session, root_ids=change.add_subtrees)
    if owner.kind == "user":
        add_subtrees &= selected_ids(
            session=session, owner=SelectionOwner.of_company(owner.company_id)
        )
    remove_subtrees = get_subtree_ids(session=session, root_ids=change.remove_subtrees)
    current = selected_ids(session=session, owner=owner)
    return (
        (current | set(change.add) | add_subtrees)
        - set(change.remove)
        - remove_subtrees
    )


def apply_change(
    *,
    session: Session,
    owner: SelectionOwner,
    change: SelectionChange,
    expected_version: int | None,
) -> JurisdictionSelectionOut:
    """Merge a change into the owner's opt-ins. The version is bumped before the
    current ids are read, so concurrent changes apply one after the other."""
    try:
        bump_version(session=session, owner=owner, expected=expected_version)
        wanted = resolve_change(session=session, owner=owner, change=change)
        _write_selection(session=session, owner=owner, wanted=wanted)
    except Exception:
        session.rollback()
        raise
    session.commit()
    return get_selection(session=session, owner=owner)
