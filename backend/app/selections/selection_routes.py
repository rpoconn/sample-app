"""Jurisdiction selections: the opt-ins of a company, of a user, and of the caller.

Every owner has the same sub-resource, `{owner}/jurisdictions`:

- GET reads the ids and the version.
- PUT replaces the set. If-Match is required, and an empty list is rejected.
- PATCH merges a SelectionChange. If-Match is optional, and checked when sent.
- DELETE clears the set. If-Match is required.

Each response carries the version as an ETag; pass it back as If-Match so a write
only lands on the selection it was based on (412 otherwise).
"""

from typing import Any

from fastapi import APIRouter, Response

from app.core.deps import IfMatchVersion, SessionDep
from app.core.errors import InvalidInput, PreconditionRequired, errors
from app.selections import selection_service
from app.selections.selection_deps import (
    CompanyReader,
    CompanyWriter,
    MyOwner,
    UserOwner,
)
from app.selections.selection_models import (
    JurisdictionSelection,
    JurisdictionSelectionOut,
    SelectionChange,
    SelectionPreview,
)
from app.selections.selection_service import SelectionOwner

users_router = APIRouter(
    prefix="/users", tags=["users"], responses=errors(401, 403, 422)
)
companies_router = APIRouter(
    prefix="/companies", tags=["companies"], responses=errors(401, 403, 422)
)


def _out(
    response: Response, owner: SelectionOwner, selection: JurisdictionSelectionOut
) -> JurisdictionSelectionOut:
    response.headers["ETag"] = owner.etag(selection.version)
    return selection


def _require_if_match(version: int | None) -> int:
    if version is None:
        raise PreconditionRequired(
            "Send If-Match with the selection's ETag; read it first with GET"
        )
    return version


def _read(
    session: SessionDep, response: Response, owner: SelectionOwner
) -> JurisdictionSelectionOut:
    return _out(
        response, owner, selection_service.get_selection(session=session, owner=owner)
    )


def _put(
    session: SessionDep,
    response: Response,
    owner: SelectionOwner,
    body: JurisdictionSelection,
    version: int | None,
) -> JurisdictionSelectionOut:
    expected = _require_if_match(version)
    if not body.jurisdiction_ids:
        raise InvalidInput(
            "Clear the selection with DELETE instead", code="use_delete_to_clear"
        )
    selection = selection_service.apply_selection(
        session=session,
        owner=owner,
        wanted=body.jurisdiction_ids,
        expected_version=expected,
    )
    return _out(response, owner, selection)


def _patch(
    session: SessionDep,
    response: Response,
    owner: SelectionOwner,
    change: SelectionChange,
    version: int | None,
) -> JurisdictionSelectionOut:
    selection = selection_service.apply_change(
        session=session, owner=owner, change=change, expected_version=version
    )
    return _out(response, owner, selection)


def _delete(
    session: SessionDep,
    response: Response,
    owner: SelectionOwner,
    version: int | None,
) -> JurisdictionSelectionOut:
    selection = selection_service.apply_selection(
        session=session,
        owner=owner,
        wanted=[],
        expected_version=_require_if_match(version),
    )
    return _out(response, owner, selection)


PUT_ERRORS = errors(404, 412, 428)
PATCH_ERRORS = errors(404, 412)


# /users/me before /users/{user_id}, so "me" never parses as an id


@users_router.get("/me/jurisdictions", response_model=JurisdictionSelectionOut)
def read_my_jurisdictions(
    session: SessionDep, response: Response, owner: MyOwner
) -> Any:
    """
    The current user's opt-ins.
    """
    return _read(session, response, owner)


@users_router.put(
    "/me/jurisdictions", response_model=JurisdictionSelectionOut, responses=PUT_ERRORS
)
def set_my_jurisdictions(
    session: SessionDep,
    response: Response,
    owner: MyOwner,
    body: JurisdictionSelection,
    version: IfMatchVersion,
) -> Any:
    """
    Replace the current user's opt-ins; each must be opted into by their company.
    """
    return _put(session, response, owner, body, version)


@users_router.patch(
    "/me/jurisdictions", response_model=JurisdictionSelectionOut, responses=PATCH_ERRORS
)
def patch_my_jurisdictions(
    session: SessionDep,
    response: Response,
    owner: MyOwner,
    body: SelectionChange,
    version: IfMatchVersion,
) -> Any:
    """
    Add or remove opt-ins for the current user. add_subtrees skips jurisdictions
    their company hasn't opted into.
    """
    return _patch(session, response, owner, body, version)


@users_router.delete(
    "/me/jurisdictions", response_model=JurisdictionSelectionOut, responses=PUT_ERRORS
)
def clear_my_jurisdictions(
    session: SessionDep, response: Response, owner: MyOwner, version: IfMatchVersion
) -> Any:
    """
    Clear the current user's opt-ins.
    """
    return _delete(session, response, owner, version)


@users_router.get(
    "/{user_id}/jurisdictions",
    response_model=JurisdictionSelectionOut,
    responses=errors(404),
)
def read_user_jurisdictions(
    session: SessionDep, response: Response, owner: UserOwner
) -> Any:
    """
    A user's opt-ins. Allowed for superusers and admins of the user's company.
    """
    return _read(session, response, owner)


@users_router.put(
    "/{user_id}/jurisdictions",
    response_model=JurisdictionSelectionOut,
    responses=PUT_ERRORS,
)
def set_user_jurisdictions(
    session: SessionDep,
    response: Response,
    owner: UserOwner,
    body: JurisdictionSelection,
    version: IfMatchVersion,
) -> Any:
    """
    Replace a user's opt-ins. Allowed for superusers and admins of the user's company.
    """
    return _put(session, response, owner, body, version)


@users_router.patch(
    "/{user_id}/jurisdictions",
    response_model=JurisdictionSelectionOut,
    responses=PATCH_ERRORS,
)
def patch_user_jurisdictions(
    session: SessionDep,
    response: Response,
    owner: UserOwner,
    body: SelectionChange,
    version: IfMatchVersion,
) -> Any:
    """
    Add or remove a user's opt-ins. Allowed for superusers and admins of the user's
    company.
    """
    return _patch(session, response, owner, body, version)


@users_router.delete(
    "/{user_id}/jurisdictions",
    response_model=JurisdictionSelectionOut,
    responses=PUT_ERRORS,
)
def clear_user_jurisdictions(
    session: SessionDep, response: Response, owner: UserOwner, version: IfMatchVersion
) -> Any:
    """
    Clear a user's opt-ins. Allowed for superusers and admins of the user's company.
    """
    return _delete(session, response, owner, version)


@companies_router.get(
    "/{company_id}/jurisdictions",
    response_model=JurisdictionSelectionOut,
    responses=errors(404),
)
def read_company_jurisdictions(
    session: SessionDep, response: Response, owner: CompanyReader
) -> Any:
    """
    Jurisdictions the company has opted into; its users may opt into these.
    """
    return _read(session, response, owner)


@companies_router.put(
    "/{company_id}/jurisdictions",
    response_model=JurisdictionSelectionOut,
    responses=PUT_ERRORS,
)
def set_company_jurisdictions(
    session: SessionDep,
    response: Response,
    owner: CompanyWriter,
    body: JurisdictionSelection,
    version: IfMatchVersion,
) -> Any:
    """
    Replace the company's opt-ins. Users lose any opt-in the company drops.
    """
    return _put(session, response, owner, body, version)


@companies_router.patch(
    "/{company_id}/jurisdictions",
    response_model=JurisdictionSelectionOut,
    responses=PATCH_ERRORS,
)
def patch_company_jurisdictions(
    session: SessionDep,
    response: Response,
    owner: CompanyWriter,
    body: SelectionChange,
    version: IfMatchVersion,
) -> Any:
    """
    Add or remove the company's opt-ins. Users lose any opt-in the company drops;
    preview the change first to see who.
    """
    return _patch(session, response, owner, body, version)


@companies_router.delete(
    "/{company_id}/jurisdictions",
    response_model=JurisdictionSelectionOut,
    responses=PUT_ERRORS,
)
def clear_company_jurisdictions(
    session: SessionDep,
    response: Response,
    owner: CompanyWriter,
    version: IfMatchVersion,
) -> Any:
    """
    Clear the company's opt-ins, and with them every opt-in of its users.
    """
    return _delete(session, response, owner, version)


# POST so a large change doesn't overflow the URL; nothing is written
@companies_router.post(
    "/{company_id}/jurisdictions/preview",
    response_model=SelectionPreview,
    responses=errors(404),
)
def preview_company_jurisdictions(
    session: SessionDep, response: Response, owner: CompanyWriter, body: SelectionChange
) -> Any:
    """
    What a PATCH with this change would add and remove, and which users would lose
    an opt-in. Send the returned version as If-Match to commit exactly this preview.
    """
    preview = selection_service.preview_company_change(
        session=session, company_id=owner.id, change=body
    )
    response.headers["ETag"] = owner.etag(preview.version)
    return preview
