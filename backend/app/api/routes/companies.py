import uuid
from typing import Any

from fastapi import APIRouter, Depends
from sqlmodel import col, func, select

from app import crud
from app.api.deps import (
    CurrentUser,
    SessionDep,
    get_current_active_superuser,
    require_company_admin,
    require_company_member,
)
from app.api.routes.jurisdictions import to_public_list
from app.errors import NotFound, errors
from app.models import (
    CompaniesPublic,
    Company,
    CompanyAdmin,
    CompanyAdmins,
    CompanyCreate,
    CompanyPublic,
    CompanyUpdate,
    JurisdictionAffectedQuery,
    JurisdictionAffectedUser,
    JurisdictionAffectedUsers,
    JurisdictionIds,
    JurisdictionSelection,
    JurisdictionsPublic,
    JurisdictionSubtreeToggle,
    JurisdictionUserCount,
    JurisdictionUserCounts,
)

router = APIRouter(
    prefix="/companies", tags=["companies"], responses=errors(401, 403, 422)
)


@router.get(
    "/",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=CompaniesPublic,
)
def read_companies(session: SessionDep, skip: int = 0, limit: int = 100) -> Any:
    """
    Retrieve companies.
    """
    count = session.exec(select(func.count()).select_from(Company)).one()
    statement = select(Company).order_by(col(Company.name)).offset(skip).limit(limit)
    companies = session.exec(statement).all()
    return CompaniesPublic(
        data=[CompanyPublic.model_validate(c) for c in companies], count=count
    )


@router.post(
    "/",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=CompanyPublic,
    responses=errors(409),
)
def create_company(*, session: SessionDep, company_in: CompanyCreate) -> Any:
    """
    Create new company.
    """
    return crud.create_company(session=session, company_in=company_in)


@router.get("/{company_id}", response_model=CompanyPublic, responses=errors(404))
def read_company(
    session: SessionDep, current_user: CurrentUser, company_id: uuid.UUID
) -> Any:
    """
    Get a company by id. Members can read their own company.
    """
    require_company_member(current_user, company_id)
    company = session.get(Company, company_id)
    if not company:
        raise NotFound("Company not found", code="company_not_found")
    return company


@router.patch(
    "/{company_id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=CompanyPublic,
    responses=errors(404, 409),
)
def update_company(
    *, session: SessionDep, company_id: uuid.UUID, company_in: CompanyUpdate
) -> Any:
    """
    Update a company.
    """
    company = session.get(Company, company_id)
    if not company:
        raise NotFound("Company not found", code="company_not_found")
    return crud.update_company(session=session, db_obj=company, company_in=company_in)


@router.get("/{company_id}/admins", response_model=CompanyAdmins)
def read_company_admins(
    session: SessionDep, current_user: CurrentUser, company_id: uuid.UUID
) -> Any:
    """
    The company's active admins, so members know who to ask for a change.
    """
    require_company_member(current_user, company_id)
    admins = crud.get_company_admins(session=session, company_id=company_id)
    return CompanyAdmins(data=[CompanyAdmin.model_validate(a) for a in admins])


@router.get("/{company_id}/jurisdictions", response_model=JurisdictionsPublic)
def read_company_jurisdictions(
    session: SessionDep, current_user: CurrentUser, company_id: uuid.UUID
) -> Any:
    """
    Jurisdictions the company has opted into; its users may opt into these.
    """
    require_company_member(current_user, company_id)
    rows = crud.get_company_jurisdictions(session=session, company_id=company_id)
    return to_public_list(session, rows)


@router.get("/{company_id}/jurisdictions/ids", response_model=JurisdictionIds)
def read_company_jurisdiction_ids(
    session: SessionDep, current_user: CurrentUser, company_id: uuid.UUID
) -> Any:
    """
    Ids of the jurisdictions the company has opted into.
    """
    require_company_member(current_user, company_id)
    rows = crud.get_company_jurisdictions(session=session, company_id=company_id)
    return JurisdictionIds(jurisdiction_ids=[j.id for j in rows], count=len(rows))


@router.put(
    "/{company_id}/jurisdictions",
    response_model=JurisdictionsPublic,
    responses=errors(404),
)
def set_company_jurisdictions(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    company_id: uuid.UUID,
    body: JurisdictionSelection,
) -> Any:
    """
    Replace the company's opt-ins. Users lose any opt-in the company drops.
    """
    require_company_admin(current_user, company_id)
    rows = crud.set_company_jurisdictions(
        session=session, company_id=company_id, jurisdiction_ids=body.jurisdiction_ids
    )
    return to_public_list(session, rows)


@router.post(
    "/{company_id}/jurisdictions/subtree",
    response_model=JurisdictionIds,
    responses=errors(404),
)
def toggle_company_jurisdiction_subtree(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    company_id: uuid.UUID,
    body: JurisdictionSubtreeToggle,
) -> Any:
    """
    Turn a jurisdiction and everything under it on or off for the company in one
    save. Users lose any opt-in the company drops.
    """
    require_company_admin(current_user, company_id)
    rows = crud.toggle_company_subtree(
        session=session,
        company_id=company_id,
        root_id=body.root_id,
        enabled=body.enabled,
    )
    return JurisdictionIds(jurisdiction_ids=[j.id for j in rows], count=len(rows))


@router.get(
    "/{company_id}/jurisdictions/user-counts", response_model=JurisdictionUserCounts
)
def read_company_jurisdiction_user_counts(
    session: SessionDep, current_user: CurrentUser, company_id: uuid.UUID
) -> Any:
    """
    How many users have opted into each of the company's jurisdictions, so admins can
    see who loses an opt-in before dropping it. Jurisdictions with no users are omitted.
    """
    require_company_admin(current_user, company_id)
    rows = crud.get_company_jurisdiction_user_counts(
        session=session, company_id=company_id
    )
    return JurisdictionUserCounts(
        data=[JurisdictionUserCount(jurisdiction_id=j, user_count=n) for j, n in rows]
    )


# POST so a large subtree of ids doesn't overflow the URL; nothing is changed
@router.post(
    "/{company_id}/jurisdictions/affected-users",
    response_model=JurisdictionAffectedUsers,
)
def read_company_jurisdiction_affected_users(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    company_id: uuid.UUID,
    body: JurisdictionAffectedQuery,
) -> Any:
    """
    Users who would lose an opt-in if the company dropped these jurisdictions, and
    everything under root_ids, so admins can see exactly who is affected first.
    """
    require_company_admin(current_user, company_id)
    ids = set(body.jurisdiction_ids) | crud.get_subtree_ids(
        session=session, root_ids=body.root_ids
    )
    rows = crud.get_company_jurisdiction_affected_users(
        session=session, company_id=company_id, jurisdiction_ids=ids
    )
    return JurisdictionAffectedUsers(
        data=[
            JurisdictionAffectedUser(
                id=u.id, email=u.email, full_name=u.full_name, jurisdiction_count=n
            )
            for u, n in rows
        ],
        count=len(rows),
    )
