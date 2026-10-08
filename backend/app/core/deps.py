import re
from collections.abc import Generator
from typing import Annotated, NamedTuple

from fastapi import Depends, Header
from sqlmodel import Session

from app.core.db import engine
from app.core.errors import PreconditionFailed


def get_db() -> Generator[Session]:
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_db)]


# A selection's ETag, W/"c-<id>-<version>", or the bare version number
_IF_MATCH = re.compile(r'^(?:W/)?"?(?:([cu]-[0-9a-fA-F-]{36})-)?(\d+)"?$')


class IfMatch(NamedTuple):
    version: int
    # The ETag's owner, "c-<id>" or "u-<id>"; None for a bare version number
    tag: str | None


def if_match_header(
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> IfMatch | None:
    """The version and owner an If-Match header names, or None when it wasn't sent."""
    if if_match is None:
        return None
    match = _IF_MATCH.match(if_match.strip())
    if not match:
        raise PreconditionFailed(
            "If-Match must be the selection's ETag or version",
            code="invalid_if_match",
        )
    tag, version = match.groups()
    return IfMatch(int(version), tag.lower() if tag else None)


IfMatchDep = Annotated[IfMatch | None, Depends(if_match_header)]
