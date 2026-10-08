"""View models for the jurisdiction grid.

These shape data for one screen and change with it: rows come pre-flattened, indented
and annotated with grid state. Integrations must use the resource endpoints
(`/jurisdictions`, `{owner}/jurisdictions`) instead.
"""

from typing import Any

from fastapi import APIRouter

from app import crud
from app import jurisdiction_query as jq
from app.api.deps import CurrentUser, SessionDep
from app.errors import errors
from app.models import (
    CompanyRole,
    JurisdictionFacets,
    JurisdictionFacetsQuery,
    JurisdictionRowsPage,
    JurisdictionRowsQuery,
)

router = APIRouter(
    prefix="/views/jurisdiction-grid",
    tags=["views"],
    responses=errors(401, 403, 422),
)


# POST so filters and expansion don't overflow the URL; nothing is changed
@router.post("/rows", response_model=JurisdictionRowsPage)
def read_jurisdiction_rows(
    session: SessionDep, current_user: CurrentUser, query: JurisdictionRowsQuery
) -> Any:
    """
    A window of the grid: matches plus the ancestors kept for context, flattened in
    sibling order through the expanded rows. sort_by=enabled checks the scope's opt-ins.
    """
    if query.sort_by is None:
        index = crud.get_canonical_tree(session=session).index
    else:
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
    index = crud.get_canonical_tree(session=session).index
    sel = crud.get_jurisdiction_selection(
        session=session, user=current_user, scope=query.scope
    )
    return jq.build_facets(index, sel, query)
