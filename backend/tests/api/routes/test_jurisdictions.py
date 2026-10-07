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
