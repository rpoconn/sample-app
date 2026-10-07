import uuid

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app import crud
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
    return {j.id for j in crud.get_user_jurisdictions(session=db, user_id=user.id)}


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
    crud.set_company_jurisdictions(
        session=db, company_id=other.id, jurisdiction_ids=[j.id]
    )

    # The other company opted in, but the row's company_id is not the user's company
    db.add(UserJurisdiction(user_id=user.id, company_id=other.id, jurisdiction_id=j.id))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_user_can_opt_into_company_jurisdictions(db: Session) -> None:
    company = make_company(db)
    user = make_user(db, company)
    j1, j2 = make_jurisdiction(db), make_jurisdiction(db)
    crud.set_company_jurisdictions(
        session=db, company_id=company.id, jurisdiction_ids=[j1.id, j2.id]
    )

    rows = crud.set_user_jurisdictions(session=db, user=user, jurisdiction_ids=[j1.id])
    assert [j.id for j in rows] == [j1.id]

    crud.set_user_jurisdictions(session=db, user=user, jurisdiction_ids=[j2.id])
    assert user_optin_ids(db, user) == {j2.id}


def test_user_cannot_opt_into_jurisdiction_outside_company_set(db: Session) -> None:
    company = make_company(db)
    user = make_user(db, company)
    allowed, other = make_jurisdiction(db), make_jurisdiction(db)
    crud.set_company_jurisdictions(
        session=db, company_id=company.id, jurisdiction_ids=[allowed.id]
    )

    with pytest.raises(crud.NotPermittedError):
        crud.set_user_jurisdictions(
            session=db, user=user, jurisdiction_ids=[allowed.id, other.id]
        )
    assert user_optin_ids(db, user) == set()


def test_company_optout_cascades_to_users(db: Session) -> None:
    company = make_company(db)
    user = make_user(db, company)
    keep, drop = make_jurisdiction(db), make_jurisdiction(db)
    crud.set_company_jurisdictions(
        session=db, company_id=company.id, jurisdiction_ids=[keep.id, drop.id]
    )
    crud.set_user_jurisdictions(
        session=db, user=user, jurisdiction_ids=[keep.id, drop.id]
    )

    crud.set_company_jurisdictions(
        session=db, company_id=company.id, jurisdiction_ids=[keep.id]
    )
    assert user_optin_ids(db, user) == {keep.id}


def test_changing_company_clears_user_optins(db: Session) -> None:
    company, other = make_company(db), make_company(db)
    user = make_user(db, company)
    j = make_jurisdiction(db)
    crud.set_company_jurisdictions(
        session=db, company_id=company.id, jurisdiction_ids=[j.id]
    )
    crud.set_user_jurisdictions(session=db, user=user, jurisdiction_ids=[j.id])

    crud.update_user(session=db, db_user=user, user_in=UserUpdate(company_id=other.id))
    assert user.company_id == other.id
    assert user_optin_ids(db, user) == set()


def test_deleting_user_removes_optins(db: Session) -> None:
    company = make_company(db)
    user = make_user(db, company)
    j = make_jurisdiction(db)
    crud.set_company_jurisdictions(
        session=db, company_id=company.id, jurisdiction_ids=[j.id]
    )
    crud.set_user_jurisdictions(session=db, user=user, jurisdiction_ids=[j.id])
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

    with pytest.raises(crud.InvalidSelectionError):
        crud.set_company_jurisdictions(
            session=db, company_id=company.id, jurisdiction_ids=[structural.id]
        )
    with pytest.raises(crud.InvalidSelectionError):
        crud.set_company_jurisdictions(
            session=db, company_id=company.id, jurisdiction_ids=[company.id]
        )


def test_cannot_make_opted_in_jurisdiction_structural(db: Session) -> None:
    company = make_company(db)
    j = make_jurisdiction(db)
    crud.set_company_jurisdictions(
        session=db, company_id=company.id, jurisdiction_ids=[j.id]
    )

    with pytest.raises(crud.ConflictError):
        crud.update_jurisdiction(
            session=db, db_obj=j, jurisdiction_in=JurisdictionUpdate(is_structural=True)
        )


def test_delete_jurisdiction_blocked_by_children_and_optins(db: Session) -> None:
    company = make_company(db)
    parent = make_jurisdiction(db)
    child = make_jurisdiction(db, parent)
    crud.set_company_jurisdictions(
        session=db, company_id=company.id, jurisdiction_ids=[child.id]
    )

    with pytest.raises(crud.ConflictError):
        crud.delete_jurisdiction(session=db, db_obj=parent)
    with pytest.raises(crud.ConflictError):
        crud.delete_jurisdiction(session=db, db_obj=child)

    crud.set_company_jurisdictions(
        session=db, company_id=company.id, jurisdiction_ids=[]
    )
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

    with pytest.raises(crud.ConflictError):
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
        with pytest.raises(crud.ConflictError):
            crud.update_jurisdiction(
                session=db,
                db_obj=root,
                jurisdiction_in=JurisdictionUpdate(parent_id=target.id),
            )
