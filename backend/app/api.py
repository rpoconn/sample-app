from fastapi import APIRouter

from app.auth import routes as auth
from app.companies import routes as companies
from app.core.config import settings
from app.internal import health, private, service_api
from app.jurisdictions import routes as jurisdictions
from app.jurisdictions.grid import routes as jurisdiction_grid
from app.selections import routes as selections
from app.users import routes as users

api_router = APIRouter()
api_router.include_router(auth.router)
# Selections first: /users/me/jurisdictions must win over /users/{user_id}
api_router.include_router(selections.users_router)
api_router.include_router(selections.companies_router)
api_router.include_router(users.router)
api_router.include_router(health.router)
api_router.include_router(jurisdictions.router)
api_router.include_router(companies.router)
api_router.include_router(service_api.router)
api_router.include_router(jurisdiction_grid.router)


if settings.FASTAPI_ENV == "development":
    api_router.include_router(private.router)
