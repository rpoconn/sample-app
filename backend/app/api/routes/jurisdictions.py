import uuid
from collections.abc import Sequence
from typing import Any

from fastapi import APIRouter, Depends
from sqlmodel import Session, col, func, select

from app import crud
from app import jurisdiction_query as jq
from app.api.deps import CurrentUser, SessionDep, get_current_active_superuser
from app.errors import NotFound
from app.models import (
    CompanyRole,
    Jurisdiction,
    JurisdictionCreate,
    JurisdictionFacets,
    JurisdictionFacetsQuery,
    JurisdictionPublic,
    JurisdictionRowsPage,
    JurisdictionRowsQuery,
    JurisdictionsPublic,
    JurisdictionUpdate,
    Message,
    SelectionScope,
    SortDir,
    TreeSortBy,
)

router = APIRouter(prefix="/jurisdictions", tags=["jurisdictions"])


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


@router.get("/", response_model=JurisdictionsPublic)
def read_jurisdictions(
    session: SessionDep, _current_user: CurrentUser, parent_id: uuid.UUID | None = None
) -> Any:
    """
    List the children of a jurisdiction, or the root jurisdictions when no parent_id.
    """
    statement = (
        select(Jurisdiction)
        .where(Jurisdiction.parent_id == parent_id)
        .order_by(col(Jurisdiction.sort_order), col(Jurisdiction.name))
    )
    return to_public_list(session, session.exec(statement).all())


@router.get("/tree", response_model=JurisdictionsPublic)
def read_jurisdiction_tree(
    session: SessionDep,
    current_user: CurrentUser,
    sort_by: TreeSortBy | None = None,
    sort_dir: SortDir = "asc",
    scope: SelectionScope = "company",
) -> Any:
    """
    List every jurisdiction as a flat list; build the tree from parent_id.
    Siblings keep the returned order. sort_by=enabled checks the current user's
    company opt-ins (scope=company) or their own (scope=user).
    """
    rows = crud.get_jurisdiction_tree(
        session=session,
        user=current_user,
        sort_by=sort_by,
        sort_dir=sort_dir,
        scope=scope,
    )
    return to_public_list(session, rows)


# POST so filters and expansion don't overflow the URL; nothing is changed
@router.post("/rows", response_model=JurisdictionRowsPage)
def read_jurisdiction_rows(
    session: SessionDep, current_user: CurrentUser, query: JurisdictionRowsQuery
) -> Any:
    """
    A window of the grid: matches plus the ancestors kept for context, flattened in
    sibling order through the expanded rows. sort_by=enabled checks the scope's opt-ins.
    """
    index = jq.TreeIndex(
        crud.get_jurisdiction_tree(
            session=session,
            user=current_user,
            sort_by=query.sort_by,
            sort_dir=query.sort_dir,
            scope=query.scope,
        )
    )
    sel = crud.get_jurisdiction_selection(
        session=session, user=current_user, scope=query.scope
    )
    # Company admins see how many users opted into each of the company's jurisdictions
    is_admin = (
        current_user.is_superuser or current_user.company_role == CompanyRole.admin
    )
    user_counts = (
        dict(
            crud.get_company_jurisdiction_user_counts(
                session=session, company_id=current_user.company_id
            )
        )
        if query.scope == "company" and is_admin
        else None
    )
    return jq.build_rows_page(index, sel, query, user_counts)


@router.post("/facets", response_model=JurisdictionFacets)
def read_jurisdiction_facets(
    session: SessionDep, current_user: CurrentUser, query: JurisdictionFacetsQuery
) -> Any:
    """
    The filter options per region type, the picks still valid among them, and counts
    per status tab under the current search and facets.
    """
    index = jq.TreeIndex(crud.get_jurisdiction_tree(session=session, user=current_user))
    sel = crud.get_jurisdiction_selection(
        session=session, user=current_user, scope=query.scope
    )
    return jq.build_facets(index, sel, query)


@router.get("/{jurisdiction_id}", response_model=JurisdictionPublic)
def read_jurisdiction(
    session: SessionDep, _current_user: CurrentUser, jurisdiction_id: uuid.UUID
) -> Any:
    """
    Get a jurisdiction by id.
    """
    return to_public(session, [_get_or_404(session, jurisdiction_id)])[0]


@router.post(
    "/",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=JurisdictionPublic,
)
def create_jurisdiction(
    *, session: SessionDep, jurisdiction_in: JurisdictionCreate
) -> Any:
    """
    Create a jurisdiction, as a root or under parent_id.
    """
    jurisdiction = crud.create_jurisdiction(
        session=session, jurisdiction_in=jurisdiction_in
    )
    return to_public(session, [jurisdiction])[0]


@router.patch(
    "/{jurisdiction_id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=JurisdictionPublic,
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
    jurisdiction = crud.update_jurisdiction(
        session=session,
        db_obj=_get_or_404(session, jurisdiction_id),
        jurisdiction_in=jurisdiction_in,
    )
    return to_public(session, [jurisdiction])[0]


@router.delete(
    "/{jurisdiction_id}", dependencies=[Depends(get_current_active_superuser)]
)
def delete_jurisdiction(session: SessionDep, jurisdiction_id: uuid.UUID) -> Message:
    """
    Delete a leaf jurisdiction that no company has opted into.
    """
    crud.delete_jurisdiction(
        session=session, db_obj=_get_or_404(session, jurisdiction_id)
    )
    return Message(message="Jurisdiction deleted successfully")
