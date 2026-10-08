import uuid
from collections.abc import Sequence
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Response
from sqlmodel import Session, col, func, select

from app.auth.deps import CurrentUser, get_current_active_superuser
from app.core.deps import SessionDep
from app.core.errors import NotFound, errors
from app.core.schemas import Message
from app.jurisdictions import service
from app.jurisdictions.models import (
    Jurisdiction,
    JurisdictionCreate,
    JurisdictionPublic,
    JurisdictionsPublic,
    JurisdictionUpdate,
)

router = APIRouter(
    prefix="/jurisdictions",
    tags=["jurisdictions"],
    responses=errors(401, 403, 422),
)


def to_public(
    session: Session, rows: Sequence[Jurisdiction]
) -> list[JurisdictionPublic]:
    """Convert rows to the API shape, filling in child_count with one query."""
    ids = [j.id for j in rows]
    counts: dict[uuid.UUID, int] = {}
    if ids:
        statement = (
            select(Jurisdiction.parent_id, func.count())
            .where(col(Jurisdiction.parent_id).in_(ids))
            .group_by(col(Jurisdiction.parent_id))
        )
        for parent_id, n in session.exec(statement).all():
            if parent_id:
                counts[parent_id] = n
    return [
        JurisdictionPublic.model_validate(
            j, update={"child_count": counts.get(j.id, 0)}
        )
        for j in rows
    ]


def to_public_list(
    session: Session, rows: Sequence[Jurisdiction]
) -> JurisdictionsPublic:
    return JurisdictionsPublic(data=to_public(session, rows), count=len(rows))


def _get_or_404(session: Session, jurisdiction_id: uuid.UUID) -> Jurisdiction:
    jurisdiction = session.get(Jurisdiction, jurisdiction_id)
    if not jurisdiction:
        raise NotFound("Jurisdiction not found", code="jurisdiction_not_found")
    return jurisdiction


@router.get("", response_model=JurisdictionsPublic)
def read_jurisdictions(
    session: SessionDep, _current_user: CurrentUser, parent_id: uuid.UUID | None = None
) -> Any:
    """
    List the children of a jurisdiction, or the root jurisdictions when no parent_id.
    Siblings come in display order.
    """
    statement = (
        select(Jurisdiction)
        .where(Jurisdiction.parent_id == parent_id)
        .order_by(col(Jurisdiction.sort_order), col(Jurisdiction.name))
    )
    return to_public_list(session, session.exec(statement).all())


@router.get(
    "/tree",
    response_model=JurisdictionsPublic,
    responses={304: {"description": "Not modified since the ETag sent"}},
)
def read_jurisdiction_tree(
    session: SessionDep,
    _current_user: CurrentUser,
    response: Response,
    if_none_match: Annotated[str | None, Header()] = None,
) -> Any:
    """
    List every jurisdiction as a flat list; build the tree from parent_id. Parents come
    before their children, and siblings come in display order. Send the ETag back as
    If-None-Match to get a 304 when nothing changed.
    """
    tree = service.get_canonical_tree(session=session)
    headers = {"ETag": tree.etag, "Cache-Control": "private, no-cache"}
    sent = {t.strip() for t in (if_none_match or "").split(",")}
    if tree.etag in sent or "*" in sent:
        return Response(status_code=304, headers=headers)
    response.headers.update(headers)
    rows = [
        JurisdictionPublic.model_validate(
            j, update={"child_count": len(tree.index.children(j))}
        )
        for j in tree.index.nodes
    ]
    return JurisdictionsPublic(data=rows, count=len(rows))


@router.get(
    "/{jurisdiction_id}", response_model=JurisdictionPublic, responses=errors(404)
)
def read_jurisdiction(
    session: SessionDep, _current_user: CurrentUser, jurisdiction_id: uuid.UUID
) -> Any:
    """
    Get a jurisdiction by id.
    """
    return to_public(session, [_get_or_404(session, jurisdiction_id)])[0]


@router.post(
    "",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=JurisdictionPublic,
    responses=errors(409),
)
def create_jurisdiction(
    *, session: SessionDep, jurisdiction_in: JurisdictionCreate
) -> Any:
    """
    Create a jurisdiction, as a root or under parent_id.
    """
    jurisdiction = service.create_jurisdiction(
        session=session, jurisdiction_in=jurisdiction_in
    )
    return to_public(session, [jurisdiction])[0]


@router.patch(
    "/{jurisdiction_id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=JurisdictionPublic,
    responses=errors(404, 409),
)
def update_jurisdiction(
    *,
    session: SessionDep,
    jurisdiction_id: uuid.UUID,
    jurisdiction_in: JurisdictionUpdate,
) -> Any:
    """
    Rename, reorder, or move a jurisdiction. Sending parent_id: null moves it to the root.
    """
    jurisdiction = service.update_jurisdiction(
        session=session,
        db_obj=_get_or_404(session, jurisdiction_id),
        jurisdiction_in=jurisdiction_in,
    )
    return to_public(session, [jurisdiction])[0]


@router.delete(
    "/{jurisdiction_id}",
    dependencies=[Depends(get_current_active_superuser)],
    responses=errors(404, 409),
)
def delete_jurisdiction(session: SessionDep, jurisdiction_id: uuid.UUID) -> Message:
    """
    Delete a leaf jurisdiction that no company has opted into.
    """
    service.delete_jurisdiction(
        session=session, db_obj=_get_or_404(session, jurisdiction_id)
    )
    return Message(message="Jurisdiction deleted successfully")
