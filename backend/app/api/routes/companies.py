import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from sqlmodel import col, func, select

from app import crud
from app.api.deps import (
    CurrentUser,
    SessionDep,
    get_current_active_superuser,
    require_company_member,
)
from app.errors import NotFound, errors
from app.models import (
    CompaniesPublic,
    Company,
    CompanyAdmin,
    CompanyAdmins,
    CompanyCreate,
    CompanyPublic,
    CompanyUpdate,
)

router = APIRouter(
    prefix="/companies", tags=["companies"], responses=errors(401, 403, 422)
)


@router.get(
    "",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=CompaniesPublic,
)
def read_companies(
    session: SessionDep,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> Any:
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
    "",
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
    return CompanyAdmins(
        data=[CompanyAdmin.model_validate(a) for a in admins], count=len(admins)
    )
