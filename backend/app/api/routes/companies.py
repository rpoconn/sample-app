import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
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
from app.models import (
    CompaniesPublic,
    Company,
    CompanyCreate,
    CompanyPublic,
    CompanyUpdate,
    JurisdictionSelection,
    JurisdictionsPublic,
)

router = APIRouter(prefix="/companies", tags=["companies"])


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
)
def create_company(*, session: SessionDep, company_in: CompanyCreate) -> Any:
    """
    Create new company.
    """
    return crud.create_company(session=session, company_in=company_in)


@router.get("/{company_id}", response_model=CompanyPublic)
def read_company(
    session: SessionDep, current_user: CurrentUser, company_id: uuid.UUID
) -> Any:
    """
    Get a company by id. Members can read their own company.
    """
    require_company_member(current_user, company_id)
    company = session.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


@router.patch(
    "/{company_id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=CompanyPublic,
)
def update_company(
    *, session: SessionDep, company_id: uuid.UUID, company_in: CompanyUpdate
) -> Any:
    """
    Update a company.
    """
    company = session.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return crud.update_company(session=session, db_obj=company, company_in=company_in)


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


@router.put("/{company_id}/jurisdictions", response_model=JurisdictionsPublic)
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
