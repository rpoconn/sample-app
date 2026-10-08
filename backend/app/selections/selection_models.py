import uuid
from datetime import datetime
from typing import Literal

from pydantic import EmailStr
from sqlalchemy import ForeignKeyConstraint, Index
from sqlmodel import Field, SQLModel

from app.core.schemas import get_datetime_utc

# Whose opt-ins count as enabled: the company's or the current user's
SelectionScope = Literal["company", "user"]


# A company's opt-in to a jurisdiction; users of the company may only pick from these
class CompanyJurisdiction(SQLModel, table=True):
    company_id: uuid.UUID = Field(
        foreign_key="company.id", primary_key=True, ondelete="CASCADE"
    )
    # RESTRICT so deleting a jurisdiction never silently drops customer opt-ins
    jurisdiction_id: uuid.UUID = Field(
        foreign_key="jurisdiction.id", primary_key=True, ondelete="RESTRICT", index=True
    )
    created_at: datetime | None = Field(default_factory=get_datetime_utc)


# A user's opt-in to a jurisdiction. The two composite foreign keys let the database
# enforce that the user's company has opted into the jurisdiction, and removing the
# company opt-in cascades to every user opt-in for it.
class UserJurisdiction(SQLModel, table=True):
    __table_args__ = (
        ForeignKeyConstraint(
            ["user_id", "company_id"],
            ["user.id", "user.company_id"],
            name="fk_userjurisdiction_user_company",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["company_id", "jurisdiction_id"],
            ["companyjurisdiction.company_id", "companyjurisdiction.jurisdiction_id"],
            name="fk_userjurisdiction_company_optin",
            ondelete="CASCADE",
        ),
        Index(
            "ix_userjurisdiction_company_jurisdiction", "company_id", "jurisdiction_id"
        ),
    )

    user_id: uuid.UUID = Field(primary_key=True)
    jurisdiction_id: uuid.UUID = Field(primary_key=True)
    company_id: uuid.UUID
    created_at: datetime | None = Field(default_factory=get_datetime_utc)


# A company user who has opted into some of a given set of jurisdictions
class JurisdictionAffectedUser(SQLModel):
    id: uuid.UUID
    email: EmailStr
    full_name: str | None = None
    # How many of the given jurisdictions this user has selected
    jurisdiction_count: int


class JurisdictionAffectedUsers(SQLModel):
    data: list[JurisdictionAffectedUser]
    count: int


# Full set of jurisdiction ids to opt into; replaces the existing set
class JurisdictionSelection(SQLModel):
    jurisdiction_ids: list[uuid.UUID]


# A company's or user's opt-ins. version is also sent as the ETag; pass it back as
# If-Match so a write only lands on the selection it was based on.
class JurisdictionSelectionOut(SQLModel):
    jurisdiction_ids: list[uuid.UUID]
    count: int
    version: int


# Applied in order: add, add_subtrees, remove, remove_subtrees. A subtree is every
# selectable jurisdiction under the root, itself included. Ids in both add and remove
# (or in both subtree lists) are rejected.
class SelectionChange(SQLModel):
    add: list[uuid.UUID] = Field(default_factory=list)
    remove: list[uuid.UUID] = Field(default_factory=list)
    add_subtrees: list[uuid.UUID] = Field(default_factory=list)
    remove_subtrees: list[uuid.UUID] = Field(default_factory=list)


# What a change to the company's opt-ins would do; nothing is written
class SelectionPreview(SQLModel):
    # Pass back as If-Match to commit exactly this preview
    version: int
    added: list[uuid.UUID]
    removed: list[uuid.UUID]
    # Users who would lose an opt-in
    affected_users: JurisdictionAffectedUsers
