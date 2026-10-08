"""Keeping the materialized tree columns (path, depth, name_path, sort_order) right."""

import uuid

from sqlmodel import Session, col, func, select

from app.core.errors import Conflict, InvalidInput
from app.jurisdictions.jurisdiction_models import Jurisdiction


def apply_tree_position(node: Jurisdiction, parent: Jurisdiction | None) -> None:
    node.parent_id = parent.id if parent else None
    node.depth = parent.depth + 1 if parent else 0
    node.path = f"{parent.path if parent else '/'}{node.id.hex}/"
    node.name_path = f"{parent.name_path} / {node.name}" if parent else node.name


def get_parent(*, session: Session, parent_id: uuid.UUID | None) -> Jurisdiction | None:
    if parent_id is None:
        return None
    parent = session.get(Jurisdiction, parent_id)
    if not parent:
        raise InvalidInput(
            "Parent jurisdiction not found",
            code="unknown_jurisdiction",
            context={"jurisdiction_ids": [str(parent_id)]},
        )
    return parent


def check_sibling_name(
    *,
    session: Session,
    parent_id: uuid.UUID | None,
    name: str,
    exclude_id: uuid.UUID | None,
) -> None:
    statement = select(Jurisdiction.id).where(
        Jurisdiction.parent_id == parent_id, Jurisdiction.name == name
    )
    if exclude_id:
        statement = statement.where(Jurisdiction.id != exclude_id)
    if session.exec(statement).first():
        raise Conflict(
            "A jurisdiction with this name already exists under that parent",
            code="jurisdiction_name_taken",
        )


def next_sort_order(*, session: Session, parent_id: uuid.UUID | None) -> int:
    current = session.exec(
        select(func.max(Jurisdiction.sort_order)).where(
            Jurisdiction.parent_id == parent_id
        )
    ).one()
    return 0 if current is None else current + 1


def rewrite_descendants(
    *,
    session: Session,
    node: Jurisdiction,
    old_path: str,
    old_name_path: str,
    old_depth: int,
) -> None:
    """Carry a moved or renamed node's new position down to everything under it.
    path holds ids, so it only changes on a move; name_path also changes on rename."""
    if node.path == old_path and node.name_path == old_name_path:
        return
    descendants = session.exec(
        select(Jurisdiction).where(
            col(Jurisdiction.path).startswith(old_path),
            Jurisdiction.id != node.id,
        )
    ).all()
    for d in descendants:
        d.path = node.path + d.path[len(old_path) :]
        d.name_path = node.name_path + d.name_path[len(old_name_path) :]
        d.depth += node.depth - old_depth
        # The tree cache keys on max(updated_at), so rewritten rows count as edits
        d.updated_at = node.updated_at
        session.add(d)
