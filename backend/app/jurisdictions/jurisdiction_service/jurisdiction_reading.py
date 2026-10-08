import hashlib
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlmodel import Session, col, func, or_, select

from app.core.errors import InvalidInput
from app.jurisdictions.jurisdiction_models import Jurisdiction
from app.jurisdictions.tree_index import TreeIndex

# Parents before children, siblings in display order
CANONICAL_ORDER: list[Any] = [
    col(Jurisdiction.depth),
    col(Jurisdiction.sort_order),
    col(Jurisdiction.name),
]


@dataclass(frozen=True)
class CanonicalTree:
    """Every jurisdiction in canonical order, as of `key`: (row count, last edit)."""

    key: tuple[int, datetime | None]
    index: TreeIndex

    @property
    def etag(self) -> str:
        digest = hashlib.sha1(repr(self.key).encode()).hexdigest()[:16]
        return f'W/"tree-{digest}"'


# Holds the latest tree only. The key comes from the database, so a worker that
# missed an edit rebuilds rather than serving stale rows.
_tree_cache: dict[tuple[int, datetime | None], CanonicalTree] = {}


def get_canonical_tree(*, session: Session) -> CanonicalTree:
    """The tree in canonical order, rebuilt only when a jurisdiction is added,
    edited or deleted. Sorted views still query: see grid.loading.get_jurisdiction_tree."""
    count, last_edit = session.exec(
        select(func.count(), func.max(Jurisdiction.updated_at))
    ).one()
    key = (count, last_edit)
    tree = _tree_cache.get(key)
    if tree is None:
        rows = session.exec(select(Jurisdiction).order_by(*CANONICAL_ORDER)).all()
        # Copies, so the cache never holds rows bound to a closed session
        tree = CanonicalTree(
            key=key, index=TreeIndex([Jurisdiction.model_validate(j) for j in rows])
        )
        _tree_cache.clear()
        _tree_cache[key] = tree
    return tree


def get_subtree_ids(
    *, session: Session, root_ids: Iterable[uuid.UUID]
) -> set[uuid.UUID]:
    """Every non-structural jurisdiction under the roots, the roots included."""
    ids = set(root_ids)
    if not ids:
        return set()
    roots = session.exec(
        select(Jurisdiction).where(col(Jurisdiction.id).in_(ids))
    ).all()
    if missing := ids - {r.id for r in roots}:
        raise InvalidInput(
            "Unknown jurisdiction ids",
            code="unknown_jurisdiction",
            context={"jurisdiction_ids": sorted(str(i) for i in missing)},
        )
    statement = select(Jurisdiction.id).where(
        or_(*(col(Jurisdiction.path).startswith(r.path) for r in roots)),
        ~col(Jurisdiction.is_structural),
    )
    return set(session.exec(statement).all())
