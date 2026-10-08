import uuid
from typing import Any

from sqlmodel import Session, select

from app.jurisdictions.jurisdiction_models import Jurisdiction


def seed_jurisdictions(*, session: Session, nodes: list[dict[str, Any]]) -> int:
    """Insert a nested jurisdiction tree, skipping ids that already exist.

    Existing rows are left untouched so edits made through the app survive restarts.
    New rows derive path/depth/name_path from their parent's current row.
    Returns the number of rows inserted.
    """
    existing = {j.id: j for j in session.exec(select(Jurisdiction)).all()}
    created = 0

    # Depth-first so parents are always added (and flushed) before their children
    def walk(children: list[dict[str, Any]], parent: Jurisdiction | None) -> None:
        nonlocal created
        for sort_order, node in enumerate(children):
            node_id = uuid.UUID(node["id"])
            row = existing.get(node_id)
            if row is None:
                name = node["name"]
                row = Jurisdiction(
                    id=node_id,
                    parent_id=parent.id if parent else None,
                    name=name,
                    is_structural=node.get("isStructural", False),
                    code=node.get("code"),
                    region_type=node.get("regionType"),
                    sort_order=sort_order,
                    depth=parent.depth + 1 if parent else 0,
                    path=f"{parent.path if parent else '/'}{node_id.hex}/",
                    name_path=f"{parent.name_path} / {name}" if parent else name,
                )
                session.add(row)
                existing[node_id] = row
                created += 1
            walk(node.get("jurisdictions", []), row)

    walk(nodes, None)
    session.commit()
    return created
