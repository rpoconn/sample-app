import uuid

from fastapi import APIRouter, Depends

from app.auth.auth_deps import require_service_caller
from app.companies.company_deps import is_company_active
from app.core.deps import SessionDep
from app.core.errors import NotFound, errors
from app.selections import selection_service as selections
from app.users.user_models import User

# Machine-to-machine reads for other services: X-API-Key or a superuser bearer token
router = APIRouter(
    prefix="/service",
    tags=["service"],
    dependencies=[Depends(require_service_caller)],
    responses=errors(401, 403, 422),
)


@router.get("/users/{user_id}/jurisdiction-ids", responses=errors(404))
def read_user_jurisdiction_ids_for_service(
    session: SessionDep, user_id: uuid.UUID
) -> list[uuid.UUID]:
    """
    The user's active jurisdiction ids as a plain JSON array, e.g. ["…", "…"].

    An inactive user, or a user of an inactive company, monitors nothing: the
    response is [] rather than an error.
    """
    user = session.get(User, user_id)
    if not user:
        raise NotFound("User not found", code="user_not_found")
    if not user.is_active or not is_company_active(session, user):
        return []
    owner = selections.SelectionOwner.of_user(user)
    return selections.get_selection(session=session, owner=owner).jurisdiction_ids
