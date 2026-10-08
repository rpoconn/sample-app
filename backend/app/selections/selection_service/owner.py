import uuid
from dataclasses import dataclass
from typing import Literal

from app.companies.company_models import Company
from app.users.user_models import User


@dataclass(frozen=True)
class SelectionOwner:
    """Whose opt-ins: a company's, or a user's within their company."""

    kind: Literal["company", "user"]
    id: uuid.UUID
    company_id: uuid.UUID

    @classmethod
    def of_company(cls, company_id: uuid.UUID) -> SelectionOwner:
        return cls("company", company_id, company_id)

    @classmethod
    def of_user(cls, user: User) -> SelectionOwner:
        return cls("user", user.id, user.company_id)

    @property
    def tag(self) -> str:
        """The owner part of the ETag, "c-<id>" or "u-<id>"."""
        return f"{self.kind[0]}-{self.id}"

    def etag(self, version: int) -> str:
        return f'W/"{self.tag}-{version}"'


def owner_table(owner: SelectionOwner) -> type[Company] | type[User]:
    return Company if owner.kind == "company" else User
