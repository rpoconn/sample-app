import json
import uuid

from sqlmodel import Session, func, select

from app import crud
from app.core.db import JURISDICTIONS_SEED_FILE
from app.models import (
    Jurisdiction,
    JurisdictionCreate,
    JurisdictionUpdate,
    RegionType,
)
from tests.utils.utils import random_lower_string


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


def test_seed_sets_codes(db: Session) -> None:
    # Codes repeat across levels, so region_type tells them apart
    rows = db.exec(select(Jurisdiction).where(Jurisdiction.code == "CA")).all()
    assert {(r.name, r.region_type) for r in rows} == {
        ("Canada", RegionType.country),
        ("California", RegionType.subdivision),
    }

    washington = db.exec(
        select(Jurisdiction).where(Jurisdiction.name == "Washington")
    ).one()
    assert (washington.code, washington.region_type) == ("WA", RegionType.subdivision)

    # Grouping nodes have no code
    structural = db.exec(
        select(Jurisdiction).where(Jurisdiction.name == "States")
    ).one()
    assert structural.code is None and structural.region_type is None


def test_move_touches_descendants_and_refreshes_the_cached_tree(db: Session) -> None:
    def create(name: str, parent: Jurisdiction | None = None) -> Jurisdiction:
        return crud.create_jurisdiction(
            session=db,
            jurisdiction_in=JurisdictionCreate(
                name=name, parent_id=parent.id if parent else None
            ),
        )

    a, b = create(random_lower_string()), create(random_lower_string())
    child = create("Child", a)
    grandchild = create("Grandchild", child)
    before = crud.get_canonical_tree(session=db)

    crud.update_jurisdiction(
        session=db, db_obj=child, jurisdiction_in=JurisdictionUpdate(parent_id=b.id)
    )
    db.refresh(grandchild)
    assert grandchild.updated_at == child.updated_at
    assert grandchild.path.startswith(b.path)

    after = crud.get_canonical_tree(session=db)
    assert after.etag != before.etag
    cached = after.index.by_id[grandchild.id]
    assert cached.name_path == f"{b.name} / Child / Grandchild"
    assert crud.get_canonical_tree(session=db) is after
