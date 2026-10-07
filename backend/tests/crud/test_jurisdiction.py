import json
import uuid

from sqlmodel import Session, func, select

from app import crud
from app.core.db import JURISDICTIONS_SEED_FILE
from app.models import Jurisdiction


def _seed_nodes() -> list[dict]:
    return json.loads(JURISDICTIONS_SEED_FILE.read_text(encoding="utf-8"))


def _count_nodes(nodes: list[dict]) -> int:
    return sum(1 + _count_nodes(n["jurisdictions"]) for n in nodes)


def test_seed_loads_full_tree(db: Session) -> None:
    nodes = _seed_nodes()
    ids = []

    def collect(children: list[dict]) -> None:
        for n in children:
            ids.append(uuid.UUID(n["id"]))
            collect(n["jurisdictions"])

    collect(nodes)
    count = db.exec(
        select(func.count()).select_from(Jurisdiction).where(Jurisdiction.id.in_(ids))  # type: ignore[attr-defined]
    ).one()
    assert count == _count_nodes(nodes)


def test_seed_is_idempotent(db: Session) -> None:
    assert crud.seed_jurisdictions(session=db, nodes=_seed_nodes()) == 0


def test_seed_derives_tree_columns(db: Session) -> None:
    root = _seed_nodes()[0]
    child = root["jurisdictions"][1]
    grandchild = child["jurisdictions"][0]

    row = db.get(Jurisdiction, uuid.UUID(grandchild["id"]))
    assert row is not None
    assert row.parent_id == uuid.UUID(child["id"])
    assert row.depth == 2
    assert row.sort_order == 0
    assert row.is_structural == grandchild["isStructural"]
    assert row.path == (
        f"/{uuid.UUID(root['id']).hex}/{uuid.UUID(child['id']).hex}/"
        f"{uuid.UUID(grandchild['id']).hex}/"
    )
    assert row.name_path == f"{root['name']} / {child['name']} / {grandchild['name']}"
