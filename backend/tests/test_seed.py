import json

from app.seed import JURISDICTIONS_SEED_FILE, _plan_jurisdiction_ids


def _name_paths_by_id(nodes, names=()):
    for node in nodes:
        path = (*names, node["name"])
        yield node["id"], " / ".join(path)
        yield from _name_paths_by_id(node.get("jurisdictions", []), path)


def test_sample_plan_matches_prd() -> None:
    nodes = json.loads(JURISDICTIONS_SEED_FILE.read_text(encoding="utf-8"))
    names = dict(_name_paths_by_id(nodes))
    plan = {names[str(i)] for i in _plan_jurisdiction_ids(nodes)}

    assert "United States / National" in plan
    assert "United States / States / Texas" in plan
    assert "United States / States / California / State" in plan
    assert "United States / States / California / Cities / San Francisco" in plan
    assert "Canada / National" in plan
    assert "Canada / Provinces / Ontario" in plan
    assert "Canada / Territories / Yukon" in plan

    assert "United States / States / Wyoming" not in plan
    assert "United States / States / Utah" not in plan
    assert "United States / States / California / Cities / Los Angeles" not in plan
    assert "United States / Federal Districts / District of Columbia" not in plan
