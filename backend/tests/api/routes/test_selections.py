import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from httpx import Response
from sqlmodel import Session

from app.core.config import settings
from app.jurisdictions.models import Jurisdiction
from tests.api.routes.conftest import Account, Setup, make_jurisdiction
from tests.utils.selections import set_company_ids, set_user_ids
from tests.utils.utils import assert_error

API = settings.API_V1_STR


def company_url(s: Setup) -> str:
    return f"{API}/companies/{s.company.id}/jurisdictions"


def user_url(account: Account) -> str:
    return f"{API}/users/{account.user.id}/jurisdictions"


MY_URL = f"{API}/users/me/jurisdictions"


def ids(*items: Jurisdiction) -> list[str]:
    return [str(j.id) for j in items]


def selection(r: Response) -> tuple[set[str], int]:
    assert r.status_code == 200, r.text
    body: dict[str, Any] = r.json()
    assert body["count"] == len(body["jurisdiction_ids"])
    return set(body["jurisdiction_ids"]), body["version"]


def read(client: TestClient, url: str, headers: dict[str, str]) -> tuple[set[str], int]:
    return selection(client.get(url, headers=headers))


def if_match(version: int) -> dict[str, str]:
    return {"If-Match": str(version)}


def test_get_returns_ids_version_and_etag(client: TestClient, s: Setup) -> None:
    r = client.get(company_url(s), headers=s.member.headers)
    assert selection(r) == (set(), 0)
    assert r.headers["ETag"] == f'W/"c-{s.company.id}-0"'

    r = client.patch(
        company_url(s), headers=s.admin.headers, json={"add": ids(s.allowed)}
    )
    assert selection(r) == ({str(s.allowed.id)}, 1)
    assert r.headers["ETag"] == f'W/"c-{s.company.id}-1"'

    r = client.get(MY_URL, headers=s.member.headers)
    assert r.headers["ETag"] == f'W/"u-{s.member.user.id}-0"'


def test_put_requires_matching_if_match(client: TestClient, s: Setup) -> None:
    url, h = company_url(s), s.admin.headers
    body = {"jurisdiction_ids": ids(s.allowed)}

    assert_error(client.put(url, headers=h, json=body), 428, "if_match_required")

    r = client.put(url, headers={**h, **if_match(5)}, json=body)
    assert assert_error(r, 412, "version_mismatch")["context"] == {"version": 0}
    assert read(client, url, h) == (set(), 0)

    r = client.put(url, headers={**h, **if_match(0)}, json=body)
    assert selection(r) == ({str(s.allowed.id)}, 1)

    # The ETag itself works as If-Match too
    etag = r.headers["ETag"]
    body = {"jurisdiction_ids": ids(s.allowed, s.not_allowed)}
    r = client.put(url, headers={**h, "If-Match": etag}, json=body)
    assert selection(r)[1] == 2

    r = client.put(url, headers={**h, "If-Match": "bogus"}, json=body)
    assert_error(r, 412, "invalid_if_match")


def test_second_write_from_the_same_snapshot_loses(
    client: TestClient, s: Setup
) -> None:
    """The lost-update case: two admins load version 0, and both save."""
    url, h = company_url(s), s.admin.headers
    _, version = read(client, url, h)

    first = {"jurisdiction_ids": ids(s.allowed)}
    assert client.put(url, headers={**h, **if_match(version)}, json=first).is_success
    second = {"jurisdiction_ids": ids(s.not_allowed)}
    r = client.put(url, headers={**h, **if_match(version)}, json=second)
    assert_error(r, 412, "version_mismatch")
    assert read(client, url, h) == ({str(s.allowed.id)}, version + 1)


def test_clearing_takes_delete(client: TestClient, s: Setup) -> None:
    url, h = company_url(s), s.admin.headers
    selection(client.patch(url, headers=h, json={"add": ids(s.allowed)}))

    r = client.put(url, headers={**h, **if_match(1)}, json={"jurisdiction_ids": []})
    assert_error(r, 422, "use_delete_to_clear")
    assert_error(client.delete(url, headers=h), 428, "if_match_required")
    assert_error(
        client.delete(url, headers={**h, **if_match(0)}), 412, "version_mismatch"
    )

    r = client.delete(url, headers={**h, **if_match(1)})
    assert selection(r) == (set(), 2)


def test_company_drop_bumps_only_affected_users(
    client: TestClient, db: Session, s: Setup
) -> None:
    set_company_ids(db, s.company.id, [s.allowed.id, s.not_allowed.id])
    set_user_ids(db, s.admin.user, [s.allowed.id])
    set_user_ids(db, s.member.user, [s.not_allowed.id])
    _, admin_version = read(client, MY_URL, s.admin.headers)
    _, member_version = read(client, MY_URL, s.member.headers)

    r = client.patch(
        company_url(s), headers=s.admin.headers, json={"remove": ids(s.allowed)}
    )
    assert selection(r)[0] == {str(s.not_allowed.id)}

    assert read(client, MY_URL, s.admin.headers) == (set(), admin_version + 1)
    assert read(client, MY_URL, s.member.headers) == (
        {str(s.not_allowed.id)},
        member_version,
    )


def test_company_move_bumps_user_version(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
    s: Setup,
) -> None:
    set_company_ids(db, s.company.id, [s.allowed.id])
    set_user_ids(db, s.member.user, [s.allowed.id])
    _, version = read(client, user_url(s.member), superuser_token_headers)

    r = client.patch(
        f"{API}/users/{s.member.user.id}",
        headers=superuser_token_headers,
        json={"company_id": str(s.other_company.id)},
    )
    assert r.status_code == 200
    assert read(client, user_url(s.member), superuser_token_headers) == (
        set(),
        version + 1,
    )


def test_patch_merges_changes(client: TestClient, s: Setup) -> None:
    url, h = company_url(s), s.admin.headers
    selection(client.patch(url, headers=h, json={"add": ids(s.allowed)}))

    r = client.patch(url, headers=h, json={"add": ids(s.not_allowed)})
    assert selection(r)[0] == set(ids(s.allowed, s.not_allowed))
    r = client.patch(url, headers=h, json={"remove": ids(s.allowed)})
    assert selection(r)[0] == set(ids(s.not_allowed))

    r = client.patch(
        url, headers=h, json={"add": ids(s.allowed), "remove": ids(s.allowed)}
    )
    body = assert_error(r, 422, "selection_conflict")
    assert body["context"]["jurisdiction_ids"] == ids(s.allowed)

    r = client.patch(url, headers=h, json={"add": ids(s.structural)})
    assert_error(r, 422, "jurisdiction_structural")
    r = client.patch(url, headers=h, json={"add_subtrees": [str(uuid.uuid4())]})
    assert_error(r, 422, "unknown_jurisdiction")

    # If-Match is optional on PATCH, but checked when sent
    _, version = read(client, url, h)
    r = client.patch(url, headers={**h, **if_match(version - 1)}, json={"add": []})
    assert_error(r, 412, "version_mismatch")
    r = client.patch(url, headers={**h, **if_match(version)}, json={"add": []})
    assert selection(r)[1] == version + 1


def test_subtrees(client: TestClient, db: Session, s: Setup) -> None:
    root = make_jurisdiction(db)
    group = make_jurisdiction(db, root, structural=True)
    a, b = make_jurisdiction(db, group), make_jurisdiction(db, group)

    r = client.patch(
        company_url(s), headers=s.admin.headers, json={"add_subtrees": ids(root)}
    )
    # Structural rows are never selected
    assert selection(r)[0] == set(ids(root, a, b))
    r = client.patch(
        company_url(s), headers=s.admin.headers, json={"remove_subtrees": ids(b)}
    )
    assert selection(r)[0] == set(ids(root, a))

    # A user's subtree skips what the company hasn't licensed...
    r = client.patch(MY_URL, headers=s.member.headers, json={"add_subtrees": ids(root)})
    assert selection(r)[0] == set(ids(root, a))
    # ...but an explicit add of it is rejected
    r = client.patch(MY_URL, headers=s.member.headers, json={"add": ids(b)})
    assert_error(r, 422, "jurisdiction_not_licensed")

    r = client.patch(
        MY_URL, headers=s.member.headers, json={"remove_subtrees": ids(group)}
    )
    assert selection(r)[0] == set(ids(root))


def test_preview_then_commit(client: TestClient, db: Session, s: Setup) -> None:
    set_company_ids(db, s.company.id, [s.allowed.id, s.not_allowed.id])
    set_user_ids(db, s.admin.user, [s.allowed.id, s.not_allowed.id])
    set_user_ids(db, s.member.user, [s.allowed.id])
    url, h = company_url(s), s.admin.headers
    before = read(client, url, h)
    change = {"remove": ids(s.allowed, s.not_allowed)}

    r = client.post(f"{url}/preview", headers=h, json=change)
    assert r.status_code == 200
    preview = r.json()
    assert preview["version"] == before[1]
    assert r.headers["ETag"] == f'W/"c-{s.company.id}-{before[1]}"'
    assert (preview["added"], set(preview["removed"])) == ([], set(change["remove"]))
    affected = preview["affected_users"]
    assert affected["count"] == 2
    assert {(u["email"], u["jurisdiction_count"]) for u in affected["data"]} == {
        (s.admin.user.email, 2),
        (s.member.user.email, 1),
    }
    # Nothing was written
    assert read(client, url, h) == before

    r = client.patch(url, headers={**h, **if_match(preview["version"])}, json=change)
    assert selection(r) == (set(), before[1] + 1)


def test_license_change_between_preview_and_commit(
    client: TestClient, db: Session, s: Setup
) -> None:
    set_company_ids(db, s.company.id, [s.allowed.id, s.not_allowed.id])
    url, h = company_url(s), s.admin.headers
    change = {"remove_subtrees": ids(s.allowed)}
    preview = client.post(f"{url}/preview", headers=h, json=change).json()

    # Another admin changes the license meanwhile
    selection(client.patch(url, headers=h, json={"remove": ids(s.not_allowed)}))

    r = client.patch(url, headers={**h, **if_match(preview["version"])}, json=change)
    body = assert_error(r, 412, "version_mismatch")
    assert body["context"] == {"version": preview["version"] + 1}
    assert read(client, url, h)[0] == set(ids(s.allowed))


def test_company_permissions(
    client: TestClient, superuser_token_headers: dict[str, str], s: Setup
) -> None:
    url = company_url(s)
    change = {"add": ids(s.allowed)}

    assert read(client, url, s.member.headers)[0] == set()
    assert_error(client.get(url, headers=s.other_admin.headers), 403, "forbidden")
    for account in (s.member, s.other_admin):
        r = client.patch(url, headers=account.headers, json=change)
        assert_error(r, 403, "forbidden")
        r = client.post(f"{url}/preview", headers=account.headers, json=change)
        assert_error(r, 403, "forbidden")
    assert selection(client.patch(url, headers=s.admin.headers, json=change))
    assert selection(client.patch(url, headers=superuser_token_headers, json=change))

    r = client.get(
        f"{API}/companies/{uuid.uuid4()}/jurisdictions", headers=superuser_token_headers
    )
    assert_error(r, 404, "company_not_found")


@pytest.mark.parametrize("method", ["get", "patch"])
def test_user_permissions(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
    s: Setup,
    method: str,
) -> None:
    set_company_ids(db, s.company.id, [s.allowed.id])
    url = user_url(s.member)

    def call(headers: dict[str, str]) -> Response:
        if method == "get":
            return client.get(url, headers=headers)
        return client.patch(url, headers=headers, json={"add": ids(s.allowed)})

    assert selection(call(s.admin.headers))
    assert selection(call(superuser_token_headers))
    assert_error(call(s.member.headers), 403, "forbidden")
    assert_error(call(s.other_admin.headers), 403, "forbidden")
    if method == "patch":
        assert read(client, MY_URL, s.member.headers)[0] == set(ids(s.allowed))

    # Members can't see whether another id exists; superusers get a 404
    missing = f"{API}/users/{uuid.uuid4()}/jurisdictions"
    assert_error(client.get(missing, headers=s.admin.headers), 403, "forbidden")
    assert_error(
        client.get(missing, headers=superuser_token_headers), 404, "user_not_found"
    )


def test_removed_endpoints_are_gone(client: TestClient, s: Setup) -> None:
    for method, path in [
        ("get", f"{company_url(s)}/ids"),
        ("get", f"{MY_URL}/ids"),
        ("post", f"{company_url(s)}/subtree"),
        ("post", f"{MY_URL}/subtree"),
        ("get", f"{company_url(s)}/user-counts"),
        ("post", f"{company_url(s)}/affected-users"),
    ]:
        r = client.request(method, path, headers=s.admin.headers, json={})
        assert r.status_code in (404, 405), (method, path, r.status_code)
