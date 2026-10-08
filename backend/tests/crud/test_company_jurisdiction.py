import uuid

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app import crud, errors
from app.crud import SelectionOwner
from app.models import (
    Company,
    CompanyCreate,
    Jurisdiction,
    JurisdictionCreate,
    JurisdictionUpdate,
    User,
    UserCreate,
    UserJurisdiction,
    UserUpdate,
)
from tests.utils.selections import set_company_ids, set_user_ids
from tests.utils.utils import random_email, random_lower_string


def make_company(db: Session) -> Company:
    return crud.create_company(
        session=db, company_in=CompanyCreate(name=random_lower_string())
    )


def make_user(db: Session, company: Company) -> User:
    user_in = UserCreate(
        email=random_email(), password=random_lower_string(), company_id=company.id
    )
    return crud.create_user(session=db, user_create=user_in)


def make_jurisdiction(
    db: Session, parent: Jurisdiction | None = None, *, structural: bool = False
) -> Jurisdiction:
    return crud.create_jurisdiction(
        session=db,
        jurisdiction_in=JurisdictionCreate(
            name=random_lower_string(),
            parent_id=parent.id if parent else None,
            is_structural=structural,
        ),
    )


def user_optin_ids(db: Session, user: User) -> set[uuid.UUID]:
    owner = SelectionOwner.of_user(user)
    return set(crud.get_selection(session=db, owner=owner).jurisdiction_ids)


def test_db_rejects_user_optin_company_has_not_made(db: Session) -> None:
    company = make_company(db)
    user = make_user(db, company)
    j = make_jurisdiction(db)

    db.add(
        UserJurisdiction(user_id=user.id, company_id=company.id, jurisdiction_id=j.id)
    )
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_db_rejects_user_optin_under_another_company(db: Session) -> None:
    company, other = make_company(db), make_company(db)
    user = make_user(db, company)
    j = make_jurisdiction(db)
    set_company_ids(db, other.id, [j.id])

    # The other company opted in, but the row's company_id is not the user's company
    db.add(UserJurisdiction(user_id=user.id, company_id=other.id, jurisdiction_id=j.id))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_user_can_opt_into_company_jurisdictions(db: Session) -> None:
    company = make_company(db)
    user = make_user(db, company)
    j1, j2 = make_jurisdiction(db), make_jurisdiction(db)
    set_company_ids(db, company.id, [j1.id, j2.id])

    selection = set_user_ids(db, user, [j1.id])
    assert selection.jurisdiction_ids == [j1.id]

    set_user_ids(db, user, [j2.id])
    assert user_optin_ids(db, user) == {j2.id}


def test_user_cannot_opt_into_jurisdiction_outside_company_set(db: Session) -> None:
    company = make_company(db)
    user = make_user(db, company)
    allowed, other = make_jurisdiction(db), make_jurisdiction(db)
    set_company_ids(db, company.id, [allowed.id])

    with pytest.raises(errors.InvalidInput) as exc:
        set_user_ids(db, user, [allowed.id, other.id])
    assert exc.value.code == "jurisdiction_not_licensed"
    assert user_optin_ids(db, user) == set()


def test_company_optout_cascades_to_users(db: Session) -> None:
    company = make_company(db)
    user = make_user(db, company)
    keep, drop = make_jurisdiction(db), make_jurisdiction(db)
    set_company_ids(db, company.id, [keep.id, drop.id])
    set_user_ids(db, user, [keep.id, drop.id])

    set_company_ids(db, company.id, [keep.id])
    assert user_optin_ids(db, user) == {keep.id}


def test_changing_company_clears_user_optins(db: Session) -> None:
    company, other = make_company(db), make_company(db)
    user = make_user(db, company)
    j = make_jurisdiction(db)
    set_company_ids(db, company.id, [j.id])
    set_user_ids(db, user, [j.id])

    crud.update_user(session=db, db_user=user, user_in=UserUpdate(company_id=other.id))
    assert user.company_id == other.id
    assert user_optin_ids(db, user) == set()


def test_deleting_user_removes_optins(db: Session) -> None:
    company = make_company(db)
    user = make_user(db, company)
    j = make_jurisdiction(db)
    set_company_ids(db, company.id, [j.id])
    set_user_ids(db, user, [j.id])
    user_id = user.id

    db.delete(user)
    db.commit()
    assert (
        db.exec(
            select(UserJurisdiction).where(UserJurisdiction.user_id == user_id)
        ).all()
        == []
    )


def test_structural_and_unknown_jurisdictions_rejected(db: Session) -> None:
    company = make_company(db)
    structural = make_jurisdiction(db, structural=True)

    with pytest.raises(errors.InvalidInput):
        set_company_ids(db, company.id, [structural.id])
    with pytest.raises(errors.InvalidInput):
        set_company_ids(db, company.id, [company.id])


def test_cannot_make_opted_in_jurisdiction_structural(db: Session) -> None:
    company = make_company(db)
    j = make_jurisdiction(db)
    set_company_ids(db, company.id, [j.id])

    with pytest.raises(errors.Conflict):
        crud.update_jurisdiction(
            session=db, db_obj=j, jurisdiction_in=JurisdictionUpdate(is_structural=True)
        )


def test_delete_jurisdiction_blocked_by_children_and_optins(db: Session) -> None:
    company = make_company(db)
    parent = make_jurisdiction(db)
    child = make_jurisdiction(db, parent)
    set_company_ids(db, company.id, [child.id])

    with pytest.raises(errors.Conflict):
        crud.delete_jurisdiction(session=db, db_obj=parent)
    with pytest.raises(errors.Conflict):
        crud.delete_jurisdiction(session=db, db_obj=child)

    set_company_ids(db, company.id, [])
    crud.delete_jurisdiction(session=db, db_obj=child)
    crud.delete_jurisdiction(session=db, db_obj=parent)
    assert db.get(Jurisdiction, parent.id) is None


def test_create_jurisdiction_derives_tree_columns(db: Session) -> None:
    root = make_jurisdiction(db)
    first = make_jurisdiction(db, root)
    second = make_jurisdiction(db, root)

    assert (first.depth, first.sort_order, second.sort_order) == (1, 0, 1)
    assert first.path == f"/{root.id.hex}/{first.id.hex}/"
    assert first.name_path == f"{root.name} / {first.name}"


def test_duplicate_sibling_name_rejected(db: Session) -> None:
    root = make_jurisdiction(db)
    child = make_jurisdiction(db, root)

    with pytest.raises(errors.Conflict):
        crud.create_jurisdiction(
            session=db,
            jurisdiction_in=JurisdictionCreate(name=child.name, parent_id=root.id),
        )


def test_move_and_rename_rewrite_subtree(db: Session) -> None:
    old_root, new_root = make_jurisdiction(db), make_jurisdiction(db)
    node = make_jurisdiction(db, old_root)
    leaf = make_jurisdiction(db, node)

    crud.update_jurisdiction(
        session=db,
        db_obj=node,
        jurisdiction_in=JurisdictionUpdate(parent_id=new_root.id, name="Moved"),
    )
    db.refresh(leaf)
    assert node.path == f"/{new_root.id.hex}/{node.id.hex}/"
    assert leaf.path == f"/{new_root.id.hex}/{node.id.hex}/{leaf.id.hex}/"
    assert leaf.name_path == f"{new_root.name} / Moved / {leaf.name}"
    assert leaf.depth == 2

    # Explicit null moves the node to the root
    crud.update_jurisdiction(
        session=db, db_obj=node, jurisdiction_in=JurisdictionUpdate(parent_id=None)
    )
    db.refresh(leaf)
    assert (node.depth, leaf.depth) == (0, 1)
    assert leaf.path == f"/{node.id.hex}/{leaf.id.hex}/"
    assert leaf.name_path == f"Moved / {leaf.name}"


def test_move_under_own_descendant_rejected(db: Session) -> None:
    root = make_jurisdiction(db)
    child = make_jurisdiction(db, root)

    for target in (root, child):
        with pytest.raises(errors.Conflict):
            crud.update_jurisdiction(
                session=db,
                db_obj=root,
                jurisdiction_in=JurisdictionUpdate(parent_id=target.id),
            )


def test_company_jurisdiction_user_counts(db: Session) -> None:
    company, other = make_company(db), make_company(db)
    a, b = make_jurisdiction(db), make_jurisdiction(db)
    for c in (company, other):
        set_company_ids(db, c.id, [a.id, b.id])
    for user in (make_user(db, company), make_user(db, company)):
        set_user_ids(db, user, [a.id])
    # Another company's users don't count
    set_user_ids(db, make_user(db, other), [a.id, b.id])

    counts = crud.get_company_jurisdiction_user_counts(
        session=db, company_id=company.id
    )
    assert counts == [(a.id, 2)]


def test_company_jurisdiction_affected_users(db: Session) -> None:
    company, other = make_company(db), make_company(db)
    a, b, c = make_jurisdiction(db), make_jurisdiction(db), make_jurisdiction(db)
    for co in (company, other):
        set_company_ids(db, co.id, [a.id, b.id, c.id])
    both, only_a, only_c = (make_user(db, company) for _ in range(3))
    set_user_ids(db, both, [a.id, b.id])
    set_user_ids(db, only_a, [a.id])
    set_user_ids(db, only_c, [c.id])
    # Another company's users aren't affected
    set_user_ids(db, make_user(db, other), [a.id, b.id])

    rows = crud.get_company_jurisdiction_affected_users(
        session=db, company_id=company.id, jurisdiction_ids=[a.id, b.id]
    )
    # Each user once, however many of the ids they picked
    assert {(u.id, n) for u, n in rows} == {(both.id, 2), (only_a.id, 1)}
    assert (
        crud.get_company_jurisdiction_affected_users(
            session=db, company_id=company.id, jurisdiction_ids=[]
        )
        == []
    )
