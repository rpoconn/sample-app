import uuid

from fastapi import APIRouter, Depends

from app import crud
from app.api.deps import SessionDep, require_service_caller
from app.errors import NotFound
from app.models import User

# Machine-to-machine reads for other services: X-API-Key or a superuser bearer token
router = APIRouter(
    prefix="/service",
    tags=["service"],
    dependencies=[Depends(require_service_caller)],
)


@router.get("/users/{user_id}/jurisdiction-ids")
def read_user_jurisdiction_ids_for_service(
    session: SessionDep, user_id: uuid.UUID
) -> list[uuid.UUID]:
    """
    The user's active jurisdiction ids as a plain JSON array, e.g. ["…", "…"].
    """
    if not session.get(User, user_id):
        raise NotFound("User not found", code="user_not_found")
    rows = crud.get_user_jurisdictions(session=session, user_id=user_id)
    return [j.id for j in rows]
