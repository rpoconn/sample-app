import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.companies.company_models import CompanyCreate
from app.companies.company_service import create_company
from app.core.config import settings
from app.jurisdictions.jurisdiction_models import Jurisdiction
from app.selections.selection_service import SelectionOwner, get_selection_version
from tests.utils.factories import Setup, make_jurisdiction
from tests.utils.selections import set_company_ids, set_user_ids
from tests.utils.utils import assert_error, random_lower_string

API = settings.API_V1_STR


def test_list_roots_and_children(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    r = client.get(f"{API}/jurisdictions", headers=normal_user_token_headers)
    assert r.status_code == 200
    roots = r.json()["data"]
    assert roots and all(j["parent_id"] is None for j in roots)

    parent = next(j for j in roots if j["child_count"] > 0)
    r = client.get(
        f"{API}/jurisdictions",
        headers=normal_user_token_headers,
        params={"parent_id": parent["id"]},
    )
    assert r.json()["count"] == parent["child_count"]


def test_read_tree_returns_every_level(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    assert_error(client.get(f"{API}/jurisdictions/tree"), 401, "unauthorized")

    r = client.get(f"{API}/jurisdictions/tree", headers=normal_user_token_headers)
    assert r.status_code == 200
    nodes = r.json()["data"]
    assert r.json()["count"] == len(nodes)

    ids = {j["id"] for j in nodes}
    assert all(j["parent_id"] is None or j["parent_id"] in ids for j in nodes)
    assert not {"path", "depth", "sort_order"} & nodes[0].keys()
    # Parents always come before their children
    position = {j["id"]: i for i, j in enumerate(nodes)}
    assert all(
        j["parent_id"] is None or position[j["parent_id"]] < i
        for i, j in enumerate(nodes)
    )
    # The tree invariants still hold in storage
    deepest = max(nodes, key=lambda j: j["name_path"].count(" / "))
    row = db.get(Jurisdiction, uuid.UUID(deepest["id"]))
    assert row and row.depth == deepest["name_path"].count(" / ") > 1
    assert row.parent_id and row.path.endswith(f"/{row.parent_id.hex}/{row.id.hex}/")

    us = next(j for j in nodes if j["name"] == "United States")
    assert (us["code"], us["region_type"]) == ("US", "country")


def test_jurisdiction_admin_lifecycle(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    normal_user_token_headers: dict[str, str],
) -> None:
    body = {"name": random_lower_string()}
    r = client.post(
        f"{API}/jurisdictions", headers=normal_user_token_headers, json=body
    )
    assert_error(r, 403, "forbidden")

    root = client.post(
        f"{API}/jurisdictions", headers=superuser_token_headers, json=body
    ).json()
    child = client.post(
        f"{API}/jurisdictions",
        headers=superuser_token_headers,
        json={
            "name": "Child",
            "parent_id": root["id"],
            "code": "ZZ",
            "region_type": "subdivision",
        },
    ).json()
    assert child["name_path"] == f"{body['name']} / Child"
    assert (child["code"], child["region_type"]) == ("ZZ", "subdivision")

    r = client.patch(
        f"{API}/jurisdictions/{child['id']}",
        headers=superuser_token_headers,
        json={"code": None, "region_type": None},
    )
    assert (r.json()["code"], r.json()["region_type"]) == (None, None)

    r = client.patch(
        f"{API}/jurisdictions/{root['id']}",
        headers=superuser_token_headers,
        json={"name": "Renamed " + body["name"]},
    )
    assert r.status_code == 200
    r = client.get(
        f"{API}/jurisdictions/{child['id']}", headers=normal_user_token_headers
    )
    assert r.json()["name_path"] == f"Renamed {body['name']} / Child"

    r = client.delete(
        f"{API}/jurisdictions/{root['id']}", headers=superuser_token_headers
    )
    assert_error(r, 409, "jurisdiction_has_children")

    assert (
        client.delete(
            f"{API}/jurisdictions/{child['id']}", headers=superuser_token_headers
        ).status_code
        == 200
    )
    assert (
        client.delete(
            f"{API}/jurisdictions/{root['id']}", headers=superuser_token_headers
        ).status_code
        == 200
    )
    r = client.get(f"{API}/jurisdictions/{root['id']}", headers=superuser_token_headers)
    assert_error(r, 404, "jurisdiction_not_found")


def test_delete_opted_in_jurisdiction_conflicts(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    j = client.post(
        f"{API}/jurisdictions",
        headers=superuser_token_headers,
        json={"name": random_lower_string()},
    ).json()
    company = create_company(
        session=db, company_in=CompanyCreate(name=random_lower_string())
    )
    client.patch(
        f"{API}/companies/{company.id}/jurisdictions",
        headers=superuser_token_headers,
        json={"add": [j["id"]]},
    )

    r = client.delete(f"{API}/jurisdictions/{j['id']}", headers=superuser_token_headers)
    assert_error(r, 409, "jurisdiction_has_licenses")


def test_move_licensed_subtree_needs_flag(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
    s: Setup,
) -> None:
    root = make_jurisdiction(db)
    licensed = make_jurisdiction(db, root)
    target = make_jurisdiction(db)
    set_company_ids(db, s.company.id, [licensed.id])
    set_user_ids(db, s.member.user, [licensed.id])
    company, member = (
        SelectionOwner.of_company(s.company.id),
        SelectionOwner.of_user(s.member.user),
    )
    before = [get_selection_version(session=db, owner=o) for o in (company, member)]
    url = f"{API}/jurisdictions/{root.id}"

    r = client.patch(
        url, headers=superuser_token_headers, json={"parent_id": str(target.id)}
    )
    assert_error(r, 409, "jurisdiction_has_licenses")
    assert r.json()["context"] == {"company_count": 1, "jurisdiction_count": 1}

    r = client.patch(
        url,
        headers=superuser_token_headers,
        json={"parent_id": str(target.id), "allow_licensed_move": True},
    )
    assert r.status_code == 200
    assert r.json()["parent_id"] == str(target.id)
    db.expire_all()
    after = [get_selection_version(session=db, owner=o) for o in (company, member)]
    assert after == [v + 1 for v in before]
    # Renaming without a move needs no flag
    r = client.patch(
        url, headers=superuser_token_headers, json={"name": random_lower_string()}
    )
    assert r.status_code == 200


def test_move_unlicensed_subtree(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    root = make_jurisdiction(db)
    make_jurisdiction(db, root)
    target = make_jurisdiction(db)

    r = client.patch(
        f"{API}/jurisdictions/{root.id}",
        headers=superuser_token_headers,
        json={"parent_id": str(target.id)},
    )
    assert r.status_code == 200
    assert r.json()["parent_id"] == str(target.id)


def _sibling_names(nodes: list[dict], parent_id: str) -> list[str]:
    return [j["name"] for j in nodes if j["parent_id"] == parent_id]


def test_tree_etag(client: TestClient, superuser_token_headers: dict[str, str]) -> None:
    url = f"{API}/jurisdictions/tree"
    r = client.get(url, headers=superuser_token_headers)
    etag = r.headers["ETag"]
    assert etag.startswith('W/"tree-')

    unchanged = {**superuser_token_headers, "If-None-Match": etag}
    r = client.get(url, headers=unchanged)
    assert r.status_code == 304
    assert r.headers["ETag"] == etag

    root = client.post(
        f"{API}/jurisdictions",
        headers=superuser_token_headers,
        json={"name": random_lower_string()},
    ).json()
    child = client.post(
        f"{API}/jurisdictions",
        headers=superuser_token_headers,
        json={"name": "Child", "parent_id": root["id"]},
    ).json()
    r = client.get(url, headers=unchanged)
    assert r.status_code == 200
    etag = r.headers["ETag"]

    # A rename rewrites descendants' name_path, and the cached tree follows
    client.patch(
        f"{API}/jurisdictions/{root['id']}",
        headers=superuser_token_headers,
        json={"name": "Renamed " + root["name"]},
    )
    r = client.get(url, headers={**superuser_token_headers, "If-None-Match": etag})
    assert r.status_code == 200
    renamed = next(j for j in r.json()["data"] if j["id"] == child["id"])
    assert renamed["name_path"] == f"Renamed {root['name']} / Child"

    client.delete(f"{API}/jurisdictions/{child['id']}", headers=superuser_token_headers)
    nodes = client.get(url, headers=superuser_token_headers).json()["data"]
    assert child["id"] not in {j["id"] for j in nodes}


def test_rows_sort_siblings(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    root = client.post(
        f"{API}/jurisdictions",
        headers=superuser_token_headers,
        json={"name": random_lower_string()},
    ).json()
    for name in ["Bravo", "alpha", "Charlie"]:
        client.post(
            f"{API}/jurisdictions",
            headers=superuser_token_headers,
            json={"name": name, "parent_id": root["id"]},
        )
    by_id = {
        j["name"]: j["id"]
        for j in client.get(
            f"{API}/jurisdictions",
            headers=superuser_token_headers,
            params={"parent_id": root["id"]},
        ).json()["data"]
    }

    def tree(**query: str) -> list[str]:
        r = client.post(
            f"{API}/views/jurisdiction-grid/rows",
            headers=superuser_token_headers,
            json={"expanded_ids": [root["id"]], "limit": 500, **query},
        )
        assert r.status_code == 200
        return _sibling_names(r.json()["data"], root["id"])

    # Default keeps insertion (sort_order) order
    assert tree() == ["Bravo", "alpha", "Charlie"]
    assert tree(sort_by="name") == ["alpha", "Bravo", "Charlie"]
    assert tree(sort_by="name", sort_dir="desc") == ["Charlie", "Bravo", "alpha"]

    me = client.get(f"{API}/users/me", headers=superuser_token_headers).json()
    client.patch(
        f"{API}/companies/{me['company_id']}/jurisdictions",
        headers=superuser_token_headers,
        json={"add": [by_id["Charlie"], by_id["Bravo"]]},
    )
    client.patch(
        f"{API}/users/me/jurisdictions",
        headers=superuser_token_headers,
        json={"add": [by_id["Bravo"]]},
    )

    assert tree(sort_by="enabled", sort_dir="desc") == ["Bravo", "Charlie", "alpha"]
    assert tree(sort_by="enabled") == ["alpha", "Bravo", "Charlie"]
    assert tree(sort_by="enabled", sort_dir="desc", scope="user") == [
        "Bravo",
        "alpha",
        "Charlie",
    ]


def test_rows_pages_the_flattened_tree(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    url = f"{API}/views/jurisdiction-grid/rows"
    assert_error(client.post(url, json={}), 401, "unauthorized")

    r = client.post(url, headers=normal_user_token_headers, json={"limit": 500})
    assert r.status_code == 200
    full = r.json()
    # Browsing opens the roots
    roots = [row for row in full["data"] if row["parent_id"] is None]
    assert {row["id"] for row in roots} == set(full["expanded_ids"])
    assert all(row["expanded"] for row in roots)
    assert full["count"] == len(full["data"])

    expanded = [row["id"] for row in full["data"]]
    everything = client.post(
        url,
        headers=normal_user_token_headers,
        json={"expanded_ids": expanded, "limit": 500},
    ).json()
    ids = [row["id"] for row in everything["data"]]
    pages: list[str] = []
    for skip in range(0, everything["count"], 7):
        page = client.post(
            url,
            headers=normal_user_token_headers,
            json={"expanded_ids": expanded, "skip": skip, "limit": 7},
        ).json()
        assert page["count"] == everything["count"]
        pages += [row["id"] for row in page["data"]]
    assert pages == ids[: len(pages)]

    bad_bodies = [{"limit": 0}, {"limit": 501}, {"skip": -1}, {"sort_by": "bogus"}]
    for bad in [*bad_bodies, {"filters": {"status": "bogus"}}]:
        r = client.post(url, headers=normal_user_token_headers, json=bad)
        assert_error(r, 422, "invalid_input")


def test_rows_filter_opens_ancestors_of_matches(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    r = client.post(
        f"{API}/views/jurisdiction-grid/rows",
        headers=superuser_token_headers,
        json={"filters": {"search": "united states"}, "limit": 500},
    )
    assert r.status_code == 200
    rows = r.json()["data"]
    us = next(row for row in rows if row["name"] == "United States")
    assert us["is_match"] and us["display_depth"] == 0
    assert us["flag_keys"] == ["US"]
    # Superusers see user counts in company scope
    assert us["user_count"] is not None

    user_scope = client.post(
        f"{API}/views/jurisdiction-grid/rows",
        headers=superuser_token_headers,
        json={"scope": "user", "filters": {"search": "united states"}},
    ).json()["data"]
    assert all(row["user_count"] is None for row in user_scope)


def test_facets(client: TestClient, normal_user_token_headers: dict[str, str]) -> None:
    url = f"{API}/views/jurisdiction-grid/facets"
    r = client.post(url, headers=normal_user_token_headers, json={})
    assert r.status_code == 200
    facets = {f["type"]: f for f in r.json()["facets"]}
    us = next(o for o in facets["country"]["options"] if o["label"] == "United States")

    r = client.post(
        url,
        headers=normal_user_token_headers,
        json={"filters": {"by_type": {"country": [us["id"]]}}},
    )
    body = r.json()
    assert body["by_type"] == {"country": [us["id"]]}
    subdivisions = {f["type"]: f for f in body["facets"]}["subdivision"]["options"]
    assert subdivisions and all(
        "US" in o["flag_keys"] or not o["flag_keys"] for o in subdivisions
    )
    counts = body["status_counts"]
    assert counts["all"] == counts["enabled"] + counts["available"] + counts["disabled"]
    assert body["summary"]["shown"] <= body["summary"]["total"]


def test_create_with_unknown_parent(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    parent_id = str(uuid.uuid4())
    r = client.post(
        f"{API}/jurisdictions",
        headers=superuser_token_headers,
        json={"name": random_lower_string(), "parent_id": parent_id},
    )
    body = assert_error(r, 422, "unknown_jurisdiction")
    assert body["context"]["jurisdiction_ids"] == [parent_id]
