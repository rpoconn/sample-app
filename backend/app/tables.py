"""Imports every module that defines a table, so SQLModel.metadata is complete for
Alembic. A new table module must be added here."""

from sqlmodel import SQLModel

from app.auth import auth_models as auth  # noqa: F401
from app.companies import company_models as companies  # noqa: F401
from app.jurisdictions import jurisdiction_models as jurisdictions  # noqa: F401
from app.selections import selection_models as selections  # noqa: F401
from app.users import user_models as users  # noqa: F401

metadata = SQLModel.metadata
