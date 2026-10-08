import uuid

from sqlmodel import Session, col, select

from app.core.errors import Conflict
from app.core.schemas import get_datetime_utc
from app.jurisdictions.jurisdiction_models import (
    Jurisdiction,
    JurisdictionCreate,
    JurisdictionUpdate,
)
from app.jurisdictions.jurisdiction_service.tree import (
    apply_tree_position,
    check_sibling_name,
    get_parent,
    next_sort_order,
    rewrite_descendants,
)
from app.selections.selection_models import CompanyJurisdiction, UserJurisdiction
from app.selections.selection_service.versions import (
    bump_company_versions,
    bump_user_versions,
)


def _has_company_optins(*, session: Session, jurisdiction_id: uuid.UUID) -> bool:
    statement = select(CompanyJurisdiction.company_id).where(
        CompanyJurisdiction.jurisdiction_id == jurisdiction_id
    )
    return session.exec(statement).first() is not None


def create_jurisdiction(
    *, session: Session, jurisdiction_in: JurisdictionCreate
) -> Jurisdiction:
    parent = get_parent(session=session, parent_id=jurisdiction_in.parent_id)
    check_sibling_name(
        session=session,
        parent_id=jurisdiction_in.parent_id,
        name=jurisdiction_in.name,
        exclude_id=None,
    )
    sort_order = jurisdiction_in.sort_order
    if sort_order is None:
        sort_order = next_sort_order(
            session=session, parent_id=jurisdiction_in.parent_id
        )
    db_obj = Jurisdiction(
        name=jurisdiction_in.name,
        is_structural=jurisdiction_in.is_structural,
        code=jurisdiction_in.code,
        region_type=jurisdiction_in.region_type,
        sort_order=sort_order,
        path="",
        name_path="",
    )
    apply_tree_position(db_obj, parent)
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def update_jurisdiction(
    *, session: Session, db_obj: Jurisdiction, jurisdiction_in: JurisdictionUpdate
) -> Jurisdiction:
    data = jurisdiction_in.model_dump(exclude_unset=True)
    moving = "parent_id" in data and data["parent_id"] != db_obj.parent_id
    new_parent_id = data["parent_id"] if moving else db_obj.parent_id
    new_name = data.get("name") or db_obj.name

    if data.get("is_structural") and not db_obj.is_structural:
        if _has_company_optins(session=session, jurisdiction_id=db_obj.id):
            raise Conflict(
                "Companies have opted into this jurisdiction; it cannot become structural",
                code="jurisdiction_has_licenses",
            )
    parent = get_parent(session=session, parent_id=new_parent_id)
    if parent and parent.path.startswith(db_obj.path):
        raise Conflict(
            "A jurisdiction cannot be moved under itself or its descendants",
            code="jurisdiction_cycle",
        )
    if moving or new_name != db_obj.name:
        check_sibling_name(
            session=session,
            parent_id=new_parent_id,
            name=new_name,
            exclude_id=db_obj.id,
        )
    licenses: list[tuple[uuid.UUID, uuid.UUID]] = []
    if moving:
        licenses = list(
            session.exec(
                select(
                    CompanyJurisdiction.company_id, CompanyJurisdiction.jurisdiction_id
                )
                .join(Jurisdiction)
                .where(col(Jurisdiction.path).startswith(db_obj.path))
            ).all()
        )
        if licenses and not jurisdiction_in.allow_licensed_move:
            raise Conflict(
                "Companies hold licenses in this subtree; set allow_licensed_move to move it",
                code="jurisdiction_has_licenses",
                context={
                    "company_count": len({c for c, _ in licenses}),
                    "jurisdiction_count": len({j for _, j in licenses}),
                },
            )

    old_path, old_name_path, old_depth = db_obj.path, db_obj.name_path, db_obj.depth
    db_obj.name = new_name
    if data.get("is_structural") is not None:
        db_obj.is_structural = data["is_structural"]
    # An explicit null clears the code
    if "code" in data:
        db_obj.code = data["code"]
    if "region_type" in data:
        db_obj.region_type = data["region_type"]
    if data.get("sort_order") is not None:
        db_obj.sort_order = data["sort_order"]
    elif moving:
        db_obj.sort_order = next_sort_order(session=session, parent_id=new_parent_id)
    apply_tree_position(db_obj, parent)
    db_obj.updated_at = get_datetime_utc()
    rewrite_descendants(
        session=session,
        node=db_obj,
        old_path=old_path,
        old_name_path=old_name_path,
        old_depth=old_depth,
    )

    # Selections list ids in name-path order, so a move changes what holders read back
    if licenses:
        bump_company_versions(session=session, company_ids={c for c, _ in licenses})
        moved_ids = {j for _, j in licenses}
        bump_user_versions(
            session=session,
            user_ids=select(UserJurisdiction.user_id)
            .where(col(UserJurisdiction.jurisdiction_id).in_(moved_ids))
            .distinct(),
        )

    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def delete_jurisdiction(*, session: Session, db_obj: Jurisdiction) -> None:
    has_children = session.exec(
        select(Jurisdiction.id).where(Jurisdiction.parent_id == db_obj.id)
    ).first()
    if has_children:
        raise Conflict(
            "Jurisdiction has children; delete or move them first",
            code="jurisdiction_has_children",
        )
    if _has_company_optins(session=session, jurisdiction_id=db_obj.id):
        raise Conflict(
            "Companies have opted into this jurisdiction; remove those opt-ins first",
            code="jurisdiction_has_licenses",
        )
    session.delete(db_obj)
    session.commit()
