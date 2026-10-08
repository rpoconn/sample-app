import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session

from app import crud
from app.core.config import settings
from app.models import CompanyCreate
from tests.utils.utils import random_lower_string

API = settings.API_V1_STR


def test_list_roots_and_children(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    r = client.get(f"{API}/jurisdictions/", headers=normal_user_token_headers)
    assert r.status_code == 200
    roots = r.json()["data"]
    assert roots and all(j["parent_id"] is None for j in roots)

    parent = next(j for j in roots if j["child_count"] > 0)
    r = client.get(
        f"{API}/jurisdictions/",
        headers=normal_user_token_headers,
        params={"parent_id": parent["id"]},
    )
    assert r.json()["count"] == parent["child_count"]


def test_read_tree_returns_every_level(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    assert client.get(f"{API}/jurisdictions/tree").status_code == 401

    r = client.get(f"{API}/jurisdictions/tree", headers=normal_user_token_headers)
    assert r.status_code == 200
    nodes = r.json()["data"]
    assert r.json()["count"] == len(nodes)

    ids = {j["id"] for j in nodes}
    assert all(j["parent_id"] is None or j["parent_id"] in ids for j in nodes)
    assert max(j["depth"] for j in nodes) > 1
    # Parents always come before their children
    depths = [j["depth"] for j in nodes]
    assert depths == sorted(depths)

    us = next(j for j in nodes if j["name"] == "United States")
    assert (us["code"], us["region_type"]) == ("US", "country")


def test_jurisdiction_admin_lifecycle(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    normal_user_token_headers: dict[str, str],
) -> None:
    body = {"name": random_lower_string()}
    assert (
        client.post(
            f"{API}/jurisdictions/", headers=normal_user_token_headers, json=body
        ).status_code
        == 403
    )

    root = client.post(
        f"{API}/jurisdictions/", headers=superuser_token_headers, json=body
    ).json()
    child = client.post(
        f"{API}/jurisdictions/",
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
    assert r.status_code == 409

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
    assert (
        client.get(
            f"{API}/jurisdictions/{root['id']}", headers=superuser_token_headers
        ).status_code
        == 404
    )


def test_delete_opted_in_jurisdiction_conflicts(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    j = client.post(
        f"{API}/jurisdictions/",
        headers=superuser_token_headers,
        json={"name": random_lower_string()},
    ).json()
    company = crud.create_company(
        session=db, company_in=CompanyCreate(name=random_lower_string())
    )
    client.put(
        f"{API}/companies/{company.id}/jurisdictions",
        headers=superuser_token_headers,
        json={"jurisdiction_ids": [j["id"]]},
    )

    r = client.delete(f"{API}/jurisdictions/{j['id']}", headers=superuser_token_headers)
    assert r.status_code == 409


def _sibling_names(nodes: list[dict], parent_id: str) -> list[str]:
    return [j["name"] for j in nodes if j["parent_id"] == parent_id]


def test_read_tree_sorts_siblings(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    root = client.post(
        f"{API}/jurisdictions/",
        headers=superuser_token_headers,
        json={"name": random_lower_string()},
    ).json()
    for name in ["Bravo", "alpha", "Charlie"]:
        client.post(
            f"{API}/jurisdictions/",
            headers=superuser_token_headers,
            json={"name": name, "parent_id": root["id"]},
        )
    by_id = {
        j["name"]: j["id"]
        for j in client.get(
            f"{API}/jurisdictions/",
            headers=superuser_token_headers,
            params={"parent_id": root["id"]},
        ).json()["data"]
    }

    def tree(**params: str) -> list[str]:
        r = client.get(
            f"{API}/jurisdictions/tree", headers=superuser_token_headers, params=params
        )
        assert r.status_code == 200
        return _sibling_names(r.json()["data"], root["id"])

    # Default keeps insertion (sort_order) order
    assert tree() == ["Bravo", "alpha", "Charlie"]
    assert tree(sort_by="name") == ["alpha", "Bravo", "Charlie"]
    assert tree(sort_by="name", sort_dir="desc") == ["Charlie", "Bravo", "alpha"]

    me = client.get(f"{API}/users/me", headers=superuser_token_headers).json()
    company_ids = [
        j["id"]
        for j in client.get(
            f"{API}/companies/{me['company_id']}/jurisdictions",
            headers=superuser_token_headers,
        ).json()["data"]
    ]
    client.put(
        f"{API}/companies/{me['company_id']}/jurisdictions",
        headers=superuser_token_headers,
        json={"jurisdiction_ids": [*company_ids, by_id["Charlie"], by_id["Bravo"]]},
    )
    client.put(
        f"{API}/users/me/jurisdictions",
        headers=superuser_token_headers,
        json={"jurisdiction_ids": [by_id["Bravo"]]},
    )

    assert tree(sort_by="enabled", sort_dir="desc") == ["Bravo", "Charlie", "alpha"]
    assert tree(sort_by="enabled") == ["alpha", "Bravo", "Charlie"]
    assert tree(sort_by="enabled", sort_dir="desc", scope="user") == [
        "Bravo",
        "alpha",
        "Charlie",
    ]

    r = client.get(
        f"{API}/jurisdictions/tree",
        headers=superuser_token_headers,
        params={"sort_by": "bogus"},
    )
    assert r.status_code == 422


def test_rows_pages_the_flattened_tree(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    url = f"{API}/jurisdictions/rows"
    assert client.post(url, json={}).status_code == 401

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

    for bad in [{"limit": 0}, {"limit": 501}, {"skip": -1}, {"sort_by": "bogus"}]:
        assert (
            client.post(url, headers=normal_user_token_headers, json=bad).status_code
            == 422
        )
    bad_status = {"filters": {"status": "bogus"}}
    assert (
        client.post(url, headers=normal_user_token_headers, json=bad_status).status_code
        == 422
    )


def test_rows_filter_opens_ancestors_of_matches(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    r = client.post(
        f"{API}/jurisdictions/rows",
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
        f"{API}/jurisdictions/rows",
        headers=superuser_token_headers,
        json={"scope": "user", "filters": {"search": "united states"}},
    ).json()["data"]
    assert all(row["user_count"] is None for row in user_scope)


def test_facets(client: TestClient, normal_user_token_headers: dict[str, str]) -> None:
    url = f"{API}/jurisdictions/facets"
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


def test_subtree_toggles(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    def create(name: str, parent_id: str | None = None, **kw: object) -> str:
        r = client.post(
            f"{API}/jurisdictions/",
            headers=superuser_token_headers,
            json={"name": name, "parent_id": parent_id, **kw},
        )
        assert r.status_code == 200
        return r.json()["id"]

    root = create(random_lower_string())
    group = create("Group", root, is_structural=True)
    a = create("A", group)
    b = create("B", group)

    me = client.get(f"{API}/users/me", headers=superuser_token_headers).json()
    company_url = f"{API}/companies/{me['company_id']}/jurisdictions"

    r = client.post(
        f"{company_url}/subtree",
        headers=superuser_token_headers,
        json={"root_id": root, "enabled": True},
    )
    assert r.status_code == 200
    company_ids = set(r.json()["jurisdiction_ids"])
    # Structural rows are never selected
    assert {root, a, b} <= company_ids and group not in company_ids

    # Users can only pick what the company licensed
    client.post(
        f"{company_url}/subtree",
        headers=superuser_token_headers,
        json={"root_id": b, "enabled": False},
    )
    r = client.post(
        f"{API}/users/me/jurisdictions/subtree",
        headers=superuser_token_headers,
        json={"root_id": root, "enabled": True},
    )
    assert r.status_code == 200
    mine = set(r.json()["jurisdiction_ids"])
    assert {root, a} <= mine and b not in mine

    r = client.post(
        f"{company_url}/affected-users",
        headers=superuser_token_headers,
        json={"root_ids": [group]},
    )
    assert me["id"] in {u["id"] for u in r.json()["data"]}

    r = client.post(
        f"{API}/users/me/jurisdictions/subtree",
        headers=superuser_token_headers,
        json={"root_id": group, "enabled": False},
    )
    mine = set(r.json()["jurisdiction_ids"])
    assert root in mine and a not in mine

    r = client.post(
        f"{API}/users/me/jurisdictions/subtree",
        headers=superuser_token_headers,
        json={"root_id": str(uuid.uuid4()), "enabled": True},
    )
    assert r.status_code == 422
    assert r.json()["code"] == "unknown_jurisdiction"


def test_create_with_unknown_parent(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    parent_id = str(uuid.uuid4())
    r = client.post(
        f"{API}/jurisdictions/",
        headers=superuser_token_headers,
        json={"name": random_lower_string(), "parent_id": parent_id},
    )
    assert r.status_code == 422
    body = r.json()
    assert body["code"] == "unknown_jurisdiction"
    assert body["context"]["jurisdiction_ids"] == [parent_id]
