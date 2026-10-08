from fastapi import APIRouter

from app.api.routes import (
    companies,
    jurisdictions,
    login,
    private,
    service,
    users,
    utils,
)
from app.core.config import settings

api_router = APIRouter()
api_router.include_router(login.router)
api_router.include_router(users.router)
api_router.include_router(utils.router)
api_router.include_router(jurisdictions.router)
api_router.include_router(companies.router)
api_router.include_router(service.router)


if settings.FASTAPI_ENV == "development":
    api_router.include_router(private.router)
