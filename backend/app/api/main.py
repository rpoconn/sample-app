from fastapi import APIRouter

from app.api.routes import (
    companies,
    jurisdictions,
    login,
    private,
    selections,
    service,
    users,
    utils,
)
from app.core.config import settings

api_router = APIRouter()
api_router.include_router(login.router)
# Selections first: /users/me/jurisdictions must win over /users/{user_id}
api_router.include_router(selections.users_router)
api_router.include_router(selections.companies_router)
api_router.include_router(users.router)
api_router.include_router(utils.router)
api_router.include_router(jurisdictions.router)
api_router.include_router(companies.router)
api_router.include_router(service.router)


if settings.FASTAPI_ENV == "development":
    api_router.include_router(private.router)
