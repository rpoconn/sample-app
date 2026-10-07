import uuid
from collections.abc import Iterable
from typing import Any, Literal

from sqlmodel import Session, case, col, delete, func, select

from app.core.security import get_password_hash, verify_password
from app.models import (
    DEFAULT_COMPANY_ID,
    Company,
    CompanyCreate,
    CompanyJurisdiction,
    CompanyRole,
    CompanyUpdate,
    Item,
    ItemCreate,
    Jurisdiction,
    JurisdictionCreate,
    JurisdictionUpdate,
    User,
    UserCreate,
    UserJurisdiction,
    UserUpdate,
    get_datetime_utc,
)


# Raised for rule violations; app.main maps status_code onto the HTTP response
class CrudError(Exception):
    status_code = 400

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class NotFoundError(CrudError):
    status_code = 404


class ConflictError(CrudError):
    status_code = 409


class InvalidSelectionError(CrudError):
    status_code = 422


class NotPermittedError(CrudError):
    status_code = 403


def _get_company(*, session: Session, company_id: uuid.UUID) -> Company:
    company = session.get(Company, company_id)
    if not company:
        raise NotFoundError("Company not found")
    return company


def create_user(*, session: Session, user_create: UserCreate) -> User:
    company_id = user_create.company_id or DEFAULT_COMPANY_ID
    _get_company(session=session, company_id=company_id)
    db_obj = User.model_validate(
        user_create,
        update={
            "hashed_password": get_password_hash(user_create.password),
            "company_id": company_id,
        },
    )
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def update_user(*, session: Session, db_user: User, user_in: UserUpdate) -> Any:
    user_data = user_in.model_dump(exclude_unset=True)
    # Company membership can be changed but never cleared
    for key in ("company_id", "company_role"):
        if key in user_data and user_data[key] is None:
            del user_data[key]
    extra_data = {}
    if "password" in user_data:
        password = user_data["password"]
        hashed_password = get_password_hash(password)
        extra_data["hashed_password"] = hashed_password
    new_company_id = user_data.get("company_id")
    if new_company_id and new_company_id != db_user.company_id:
        _get_company(session=session, company_id=new_company_id)
        # Opt-ins belong to the old company; the FK rejects the move while they exist
        session.exec(
            delete(UserJurisdiction).where(col(UserJurisdiction.user_id) == db_user.id)
        )
    db_user.sqlmodel_update(user_data, update=extra_data)
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return db_user


def get_user_by_email(*, session: Session, email: str) -> User | None:
    statement = select(User).where(User.email == email)
    session_user = session.exec(statement).first()
    return session_user


# Dummy hash to use for timing attack prevention when user is not found
# This is an Argon2 hash of a random password, used to ensure constant-time comparison
DUMMY_HASH = "$argon2id$v=19$m=65536,t=3,p=4$MjQyZWE1MzBjYjJlZTI0Yw$YTU4NGM5ZTZmYjE2NzZlZjY0ZWY3ZGRkY2U2OWFjNjk"


def authenticate(*, session: Session, email: str, password: str) -> User | None:
    db_user = get_user_by_email(session=session, email=email)
    if not db_user:
        # Prevent timing attacks by running password verification even when user doesn't exist
        # This ensures the response time is similar whether or not the email exists
        verify_password(password, DUMMY_HASH)
        return None
    verified, updated_password_hash = verify_password(password, db_user.hashed_password)
    if not verified:
        return None
    if updated_password_hash:
        db_user.hashed_password = updated_password_hash
        session.add(db_user)
        session.commit()
        session.refresh(db_user)
    return db_user


def create_item(*, session: Session, item_in: ItemCreate, owner_id: uuid.UUID) -> Item:
    db_item = Item.model_validate(item_in, update={"owner_id": owner_id})
    session.add(db_item)
    session.commit()
    session.refresh(db_item)
    return db_item


def seed_jurisdictions(*, session: Session, nodes: list[dict[str, Any]]) -> int:
    """Insert a nested jurisdiction tree, skipping ids that already exist.

    Existing rows are left untouched so edits made through the app survive restarts.
    New rows derive path/depth/name_path from their parent's current row.
    Returns the number of rows inserted.
    """
    existing = {j.id: j for j in session.exec(select(Jurisdiction)).all()}
    created = 0

    # Depth-first so parents are always added (and flushed) before their children
    def walk(children: list[dict[str, Any]], parent: Jurisdiction | None) -> None:
        nonlocal created
        for sort_order, node in enumerate(children):
            node_id = uuid.UUID(node["id"])
            row = existing.get(node_id)
            if row is None:
                name = node["name"]
                row = Jurisdiction(
                    id=node_id,
                    parent_id=parent.id if parent else None,
                    name=name,
                    is_structural=node.get("isStructural", False),
                    code=node.get("code"),
                    region_type=node.get("regionType"),
                    sort_order=sort_order,
                    depth=parent.depth + 1 if parent else 0,
                    path=f"{parent.path if parent else '/'}{node_id.hex}/",
                    name_path=f"{parent.name_path} / {name}" if parent else name,
                )
                session.add(row)
                existing[node_id] = row
                created += 1
            walk(node.get("jurisdictions", []), row)

    walk(nodes, None)
    session.commit()
    return created


def _apply_tree_position(node: Jurisdiction, parent: Jurisdiction | None) -> None:
    node.parent_id = parent.id if parent else None
    node.depth = parent.depth + 1 if parent else 0
    node.path = f"{parent.path if parent else '/'}{node.id.hex}/"
    node.name_path = f"{parent.name_path} / {node.name}" if parent else node.name


def _get_parent(
    *, session: Session, parent_id: uuid.UUID | None
) -> Jurisdiction | None:
    if parent_id is None:
        return None
    parent = session.get(Jurisdiction, parent_id)
    if not parent:
        raise NotFoundError("Parent jurisdiction not found")
    return parent


def _check_sibling_name(
    *,
    session: Session,
    parent_id: uuid.UUID | None,
    name: str,
    exclude_id: uuid.UUID | None,
) -> None:
    statement = select(Jurisdiction.id).where(
        Jurisdiction.parent_id == parent_id, Jurisdiction.name == name
    )
    if exclude_id:
        statement = statement.where(Jurisdiction.id != exclude_id)
    if session.exec(statement).first():
        raise ConflictError(
            "A jurisdiction with this name already exists under that parent"
        )


def _next_sort_order(*, session: Session, parent_id: uuid.UUID | None) -> int:
    current = session.exec(
        select(func.max(Jurisdiction.sort_order)).where(
            Jurisdiction.parent_id == parent_id
        )
    ).one()
    return 0 if current is None else current + 1


def _has_company_optins(*, session: Session, jurisdiction_id: uuid.UUID) -> bool:
    statement = select(CompanyJurisdiction.company_id).where(
        CompanyJurisdiction.jurisdiction_id == jurisdiction_id
    )
    return session.exec(statement).first() is not None


def create_jurisdiction(
    *, session: Session, jurisdiction_in: JurisdictionCreate
) -> Jurisdiction:
    parent = _get_parent(session=session, parent_id=jurisdiction_in.parent_id)
    _check_sibling_name(
        session=session,
        parent_id=jurisdiction_in.parent_id,
        name=jurisdiction_in.name,
        exclude_id=None,
    )
    sort_order = jurisdiction_in.sort_order
    if sort_order is None:
        sort_order = _next_sort_order(
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
    _apply_tree_position(db_obj, parent)
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
            raise ConflictError(
                "Companies have opted into this jurisdiction; it cannot become structural"
            )
    parent = _get_parent(session=session, parent_id=new_parent_id)
    if parent and parent.path.startswith(db_obj.path):
        raise ConflictError(
            "A jurisdiction cannot be moved under itself or its descendants"
        )
    if moving or new_name != db_obj.name:
        _check_sibling_name(
            session=session,
            parent_id=new_parent_id,
            name=new_name,
            exclude_id=db_obj.id,
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
        db_obj.sort_order = _next_sort_order(session=session, parent_id=new_parent_id)
    _apply_tree_position(db_obj, parent)
    db_obj.updated_at = get_datetime_utc()

    # path holds ids, so it only changes on a move; name_path also changes on rename
    if db_obj.path != old_path or db_obj.name_path != old_name_path:
        descendants = session.exec(
            select(Jurisdiction).where(
                col(Jurisdiction.path).startswith(old_path),
                Jurisdiction.id != db_obj.id,
            )
        ).all()
        for d in descendants:
            d.path = db_obj.path + d.path[len(old_path) :]
            d.name_path = db_obj.name_path + d.name_path[len(old_name_path) :]
            d.depth += db_obj.depth - old_depth
            session.add(d)

    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def delete_jurisdiction(*, session: Session, db_obj: Jurisdiction) -> None:
    has_children = session.exec(
        select(Jurisdiction.id).where(Jurisdiction.parent_id == db_obj.id)
    ).first()
    if has_children:
        raise ConflictError("Jurisdiction has children; delete or move them first")
    if _has_company_optins(session=session, jurisdiction_id=db_obj.id):
        raise ConflictError(
            "Companies have opted into this jurisdiction; remove those opt-ins first"
        )
    session.delete(db_obj)
    session.commit()


def ensure_default_company(*, session: Session, name: str) -> Company:
    company = session.get(Company, DEFAULT_COMPANY_ID)
    if not company:
        company = Company(id=DEFAULT_COMPANY_ID, name=name)
        session.add(company)
        session.commit()
        session.refresh(company)
    return company


def _check_company_name(
    *, session: Session, name: str, exclude_id: uuid.UUID | None
) -> None:
    statement = select(Company.id).where(Company.name == name)
    if exclude_id:
        statement = statement.where(Company.id != exclude_id)
    if session.exec(statement).first():
        raise ConflictError("A company with this name already exists")


def create_company(*, session: Session, company_in: CompanyCreate) -> Company:
    _check_company_name(session=session, name=company_in.name, exclude_id=None)
    db_obj = Company.model_validate(company_in)
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def update_company(
    *, session: Session, db_obj: Company, company_in: CompanyUpdate
) -> Company:
    data = company_in.model_dump(exclude_unset=True, exclude_none=True)
    if "name" in data:
        _check_company_name(session=session, name=data["name"], exclude_id=db_obj.id)
    db_obj.sqlmodel_update(data, update={"updated_at": get_datetime_utc()})
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


TreeSortBy = Literal["name", "enabled"]
SortDir = Literal["asc", "desc"]
SelectionScope = Literal["company", "user"]


def get_jurisdiction_tree(
    *,
    session: Session,
    user: User,
    sort_by: TreeSortBy | None = None,
    sort_dir: SortDir = "asc",
    scope: SelectionScope = "company",
) -> list[Jurisdiction]:
    """Every jurisdiction, flat. Only sibling order matters; the client nests by parent_id."""
    statement = select(Jurisdiction)
    name_key = func.lower(Jurisdiction.name)
    if sort_by is None:
        order: list[Any] = [
            col(Jurisdiction.depth),
            col(Jurisdiction.sort_order),
            col(Jurisdiction.name),
        ]
    elif sort_by == "name":
        key = name_key.desc() if sort_dir == "desc" else name_key.asc()
        order = [key, col(Jurisdiction.sort_order)]
    else:
        if scope == "company":
            link_id = col(CompanyJurisdiction.jurisdiction_id)
            statement = statement.outerjoin(
                CompanyJurisdiction,
                (link_id == Jurisdiction.id)
                & (col(CompanyJurisdiction.company_id) == user.company_id),
            )
        else:
            link_id = col(UserJurisdiction.jurisdiction_id)
            statement = statement.outerjoin(
                UserJurisdiction,
                (link_id == Jurisdiction.id)
                & (col(UserJurisdiction.user_id) == user.id),
            )
        # Structural nodes can't be selected, so they never count as enabled
        enabled = case(
            (link_id.is_not(None) & ~col(Jurisdiction.is_structural), 1), else_=0
        )
        key = enabled.desc() if sort_dir == "desc" else enabled.asc()
        order = [key, name_key, col(Jurisdiction.sort_order)]
    return list(session.exec(statement.order_by(*order)).all())


def get_company_admins(*, session: Session, company_id: uuid.UUID) -> list[User]:
    """Active admins of the company, for members who need one to change a setting."""
    statement = (
        select(User)
        .where(
            User.company_id == company_id,
            User.company_role == CompanyRole.admin,
            col(User.is_active),
        )
        .order_by(col(User.email))
    )
    return list(session.exec(statement).all())


def get_company_jurisdictions(
    *, session: Session, company_id: uuid.UUID
) -> list[Jurisdiction]:
    statement = (
        select(Jurisdiction)
        .join(
            CompanyJurisdiction,
            col(CompanyJurisdiction.jurisdiction_id) == Jurisdiction.id,
        )
        .where(CompanyJurisdiction.company_id == company_id)
        .order_by(col(Jurisdiction.name_path))
    )
    return list(session.exec(statement).all())


def get_company_jurisdiction_user_counts(
    *, session: Session, company_id: uuid.UUID
) -> list[tuple[uuid.UUID, int]]:
    """Users per jurisdiction within the company; jurisdictions with none are omitted."""
    statement = (
        select(UserJurisdiction.jurisdiction_id, func.count())
        .where(UserJurisdiction.company_id == company_id)
        .group_by(col(UserJurisdiction.jurisdiction_id))
    )
    return [(j, n) for j, n in session.exec(statement).all()]


def get_company_jurisdiction_affected_users(
    *, session: Session, company_id: uuid.UUID, jurisdiction_ids: Iterable[uuid.UUID]
) -> list[tuple[User, int]]:
    """Company users who selected any of the ids, with how many of them each selected."""
    ids = set(jurisdiction_ids)
    if not ids:
        return []
    statement = (
        select(User, func.count())
        .join(UserJurisdiction, col(UserJurisdiction.user_id) == User.id)
        .where(
            UserJurisdiction.company_id == company_id,
            col(UserJurisdiction.jurisdiction_id).in_(ids),
        )
        .group_by(col(User.id))
        .order_by(
            func.lower(func.coalesce(User.full_name, User.email)), col(User.email)
        )
    )
    return [(u, n) for u, n in session.exec(statement).all()]


def get_user_jurisdictions(
    *, session: Session, user_id: uuid.UUID
) -> list[Jurisdiction]:
    statement = (
        select(Jurisdiction)
        .join(
            UserJurisdiction, col(UserJurisdiction.jurisdiction_id) == Jurisdiction.id
        )
        .where(UserJurisdiction.user_id == user_id)
        .order_by(col(Jurisdiction.name_path))
    )
    return list(session.exec(statement).all())


def _validate_selectable(*, session: Session, ids: set[uuid.UUID]) -> None:
    if not ids:
        return
    rows = session.exec(select(Jurisdiction).where(col(Jurisdiction.id).in_(ids))).all()
    missing = ids - {j.id for j in rows}
    if missing:
        raise InvalidSelectionError(
            f"Unknown jurisdiction ids: {sorted(str(i) for i in missing)}"
        )
    structural = [j.name_path for j in rows if j.is_structural]
    if structural:
        raise InvalidSelectionError(
            f"Structural jurisdictions cannot be selected: {structural}"
        )


def set_company_jurisdictions(
    *, session: Session, company_id: uuid.UUID, jurisdiction_ids: Iterable[uuid.UUID]
) -> list[Jurisdiction]:
    """Replace the company's opt-ins. Removed ids cascade to its users' opt-ins."""
    _get_company(session=session, company_id=company_id)
    wanted = set(jurisdiction_ids)
    _validate_selectable(session=session, ids=wanted)
    current = set(
        session.exec(
            select(CompanyJurisdiction.jurisdiction_id).where(
                CompanyJurisdiction.company_id == company_id
            )
        ).all()
    )
    if removed := current - wanted:
        session.exec(
            delete(CompanyJurisdiction).where(
                col(CompanyJurisdiction.company_id) == company_id,
                col(CompanyJurisdiction.jurisdiction_id).in_(removed),
            )
        )
    for jurisdiction_id in wanted - current:
        session.add(
            CompanyJurisdiction(company_id=company_id, jurisdiction_id=jurisdiction_id)
        )
    session.commit()
    return get_company_jurisdictions(session=session, company_id=company_id)


def set_user_jurisdictions(
    *, session: Session, user: User, jurisdiction_ids: Iterable[uuid.UUID]
) -> list[Jurisdiction]:
    """Replace the user's opt-ins; each must already be opted into by the company."""
    wanted = set(jurisdiction_ids)
    _validate_selectable(session=session, ids=wanted)
    allowed = set(
        session.exec(
            select(CompanyJurisdiction.jurisdiction_id).where(
                CompanyJurisdiction.company_id == user.company_id
            )
        ).all()
    )
    if outside := wanted - allowed:
        raise NotPermittedError(
            "The company has not opted into jurisdictions: "
            f"{sorted(str(i) for i in outside)}"
        )
    current = set(
        session.exec(
            select(UserJurisdiction.jurisdiction_id).where(
                UserJurisdiction.user_id == user.id
            )
        ).all()
    )
    if removed := current - wanted:
        session.exec(
            delete(UserJurisdiction).where(
                col(UserJurisdiction.user_id) == user.id,
                col(UserJurisdiction.jurisdiction_id).in_(removed),
            )
        )
    for jurisdiction_id in wanted - current:
        session.add(
            UserJurisdiction(
                user_id=user.id,
                company_id=user.company_id,
                jurisdiction_id=jurisdiction_id,
            )
        )
    session.commit()
    return get_user_jurisdictions(session=session, user_id=user.id)
