import uuid

from fastapi import APIRouter, Depends

from app import crud
from app.api.deps import SessionDep, is_company_active, require_service_caller
from app.errors import NotFound, errors
from app.models import User

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
    rows = crud.get_user_jurisdictions(session=session, user_id=user_id)
    return [j.id for j in rows]
