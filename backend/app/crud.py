import hashlib
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from sqlalchemy import update
from sqlmodel import Session, case, col, delete, func, or_, select

from app.core.security import get_password_hash, verify_password
from app.errors import Conflict, InvalidInput, NotFound, PreconditionFailed
from app.jurisdiction_query import Selection, TreeIndex
from app.models import (
    DEFAULT_COMPANY_ID,
    Company,
    CompanyCreate,
    CompanyJurisdiction,
    CompanyRole,
    CompanyUpdate,
    Jurisdiction,
    JurisdictionAffectedUser,
    JurisdictionAffectedUsers,
    JurisdictionCreate,
    JurisdictionSelectionOut,
    JurisdictionUpdate,
    SelectionChange,
    SelectionPreview,
    SelectionScope,
    SortDir,
    TreeSortBy,
    User,
    UserCreate,
    UserJurisdiction,
    UserUpdate,
    get_datetime_utc,
)


def _get_company(*, session: Session, company_id: uuid.UUID) -> Company:
    company = session.get(Company, company_id)
    if not company:
        raise NotFound("Company not found", code="company_not_found")
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


def _ensure_company_keeps_admin(
    *, session: Session, user: User, after: dict[str, Any]
) -> None:
    """Raise if `after` (the user's new field values) leaves the user's current
    company without an active admin while it still has other active users.
    A delete is checked as `after={"is_active": False}`."""
    if not (user.is_active and user.company_role == CompanyRole.admin):
        return
    stays_admin = (
        after.get("is_active", True)
        and after.get("company_role", user.company_role) == CompanyRole.admin
        and after.get("company_id", user.company_id) == user.company_id
    )
    if stays_admin:
        return
    company = session.get(Company, user.company_id)
    if not company or not company.is_active:
        return
    others = select(User.company_role).where(
        User.company_id == user.company_id,
        col(User.is_active).is_(True),
        User.id != user.id,
    )
    roles = set(session.exec(others).all())
    if roles and CompanyRole.admin not in roles:
        raise Conflict(
            "The company would be left without an active admin; promote another user first",
            code="last_company_admin",
            context={"company_id": str(user.company_id)},
        )


def _ensure_keeps_superuser(
    *, session: Session, user: User, after: dict[str, Any]
) -> None:
    """Raise if `after` removes the last active superuser. A delete is checked as
    `after={"is_active": False}`."""
    if not (user.is_active and user.is_superuser):
        return
    if after.get("is_active", True) and after.get("is_superuser", True):
        return
    other = select(User.id).where(
        col(User.is_superuser).is_(True),
        col(User.is_active).is_(True),
        User.id != user.id,
    )
    if not session.exec(other).first():
        raise Conflict("This is the last active superuser", code="last_superuser")


def update_user(*, session: Session, db_user: User, user_in: UserUpdate) -> Any:
    user_data = user_in.model_dump(exclude_unset=True)
    # Company membership can be changed but never cleared
    for key in ("company_id", "company_role"):
        if key in user_data and user_data[key] is None:
            del user_data[key]
    new_company_id = user_data.get("company_id")
    moving = new_company_id is not None and new_company_id != db_user.company_id
    if moving:
        _get_company(session=session, company_id=user_data["company_id"])
        # Admin rights don't carry across tenants
        user_data.setdefault("company_role", CompanyRole.member)
    _ensure_company_keeps_admin(session=session, user=db_user, after=user_data)
    _ensure_keeps_superuser(session=session, user=db_user, after=user_data)
    extra_data = {}
    if "password" in user_data:
        password = user_data["password"]
        hashed_password = get_password_hash(password)
        extra_data["hashed_password"] = hashed_password
    if moving:
        # Opt-ins belong to the old company; the FK rejects the move while they exist
        session.exec(
            delete(UserJurisdiction).where(col(UserJurisdiction.user_id) == db_user.id)
        )
        _bump_user_versions(session=session, user_ids=[db_user.id])
    db_user.sqlmodel_update(user_data, update=extra_data)
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return db_user


def delete_user(*, session: Session, db_user: User) -> None:
    gone = {"is_active": False}
    _ensure_company_keeps_admin(session=session, user=db_user, after=gone)
    _ensure_keeps_superuser(session=session, user=db_user, after=gone)
    session.delete(db_user)
    session.commit()


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
        raise InvalidInput(
            "Parent jurisdiction not found",
            code="unknown_jurisdiction",
            context={"jurisdiction_ids": [str(parent_id)]},
        )
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
        raise Conflict(
            "A jurisdiction with this name already exists under that parent",
            code="jurisdiction_name_taken",
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
            raise Conflict(
                "Companies have opted into this jurisdiction; it cannot become structural",
                code="jurisdiction_has_licenses",
            )
    parent = _get_parent(session=session, parent_id=new_parent_id)
    if parent and parent.path.startswith(db_obj.path):
        raise Conflict(
            "A jurisdiction cannot be moved under itself or its descendants",
            code="jurisdiction_cycle",
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
            # The tree cache keys on max(updated_at), so rewritten rows count as edits
            d.updated_at = db_obj.updated_at
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
        raise Conflict(
            "A company with this name already exists", code="company_name_taken"
        )


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
    if db_obj.id == DEFAULT_COMPANY_ID and data.get("is_active") is False:
        raise Conflict(
            "The default company can't be deactivated",
            code="cannot_deactivate_default_company",
        )
    if "name" in data:
        _check_company_name(session=session, name=data["name"], exclude_id=db_obj.id)
    db_obj.sqlmodel_update(data, update={"updated_at": get_datetime_utc()})
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


# Parents before children, siblings in display order
CANONICAL_ORDER: list[Any] = [
    col(Jurisdiction.depth),
    col(Jurisdiction.sort_order),
    col(Jurisdiction.name),
]


@dataclass(frozen=True)
class CanonicalTree:
    """Every jurisdiction in canonical order, as of `key`: (row count, last edit)."""

    key: tuple[int, datetime | None]
    index: TreeIndex

    @property
    def etag(self) -> str:
        digest = hashlib.sha1(repr(self.key).encode()).hexdigest()[:16]
        return f'W/"tree-{digest}"'


# Holds the latest tree only. The key comes from the database, so a worker that
# missed an edit rebuilds rather than serving stale rows.
_tree_cache: dict[tuple[int, datetime | None], CanonicalTree] = {}


def get_canonical_tree(*, session: Session) -> CanonicalTree:
    """The tree in canonical order, rebuilt only when a jurisdiction is added,
    edited or deleted. Sorted views still query: see get_jurisdiction_tree."""
    count, last_edit = session.exec(
        select(func.count(), func.max(Jurisdiction.updated_at))
    ).one()
    key = (count, last_edit)
    tree = _tree_cache.get(key)
    if tree is None:
        rows = session.exec(select(Jurisdiction).order_by(*CANONICAL_ORDER)).all()
        # Copies, so the cache never holds rows bound to a closed session
        tree = CanonicalTree(
            key=key, index=TreeIndex([Jurisdiction.model_validate(j) for j in rows])
        )
        _tree_cache.clear()
        _tree_cache[key] = tree
    return tree


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
        order: list[Any] = CANONICAL_ORDER
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


def _validate_selectable(*, session: Session, ids: set[uuid.UUID]) -> None:
    if not ids:
        return
    rows = session.exec(select(Jurisdiction).where(col(Jurisdiction.id).in_(ids))).all()
    missing = ids - {j.id for j in rows}
    if missing:
        raise InvalidInput(
            "Unknown jurisdiction ids",
            code="unknown_jurisdiction",
            context={"jurisdiction_ids": sorted(str(i) for i in missing)},
        )
    structural = [j for j in rows if j.is_structural]
    if structural:
        raise InvalidInput(
            "Structural jurisdictions cannot be selected",
            code="jurisdiction_structural",
            context={
                "jurisdiction_ids": sorted(str(j.id) for j in structural),
                "name_paths": sorted(j.name_path for j in structural),
            },
        )


def get_jurisdiction_selection(
    *, session: Session, user: User, scope: SelectionScope
) -> Selection:
    """The company's opt-ins, and those on in the scope shown."""
    licensed = frozenset(
        _selected_ids(session=session, owner=SelectionOwner.of_company(user.company_id))
    )
    enabled = (
        licensed
        if scope == "company"
        else frozenset(
            _selected_ids(session=session, owner=SelectionOwner.of_user(user))
        )
    )
    return Selection(scope=scope, enabled_ids=enabled, licensed_ids=licensed)


def get_subtree_ids(
    *, session: Session, root_ids: Iterable[uuid.UUID]
) -> set[uuid.UUID]:
    """Every non-structural jurisdiction under the roots, the roots included."""
    ids = set(root_ids)
    if not ids:
        return set()
    roots = session.exec(
        select(Jurisdiction).where(col(Jurisdiction.id).in_(ids))
    ).all()
    if missing := ids - {r.id for r in roots}:
        raise InvalidInput(
            "Unknown jurisdiction ids",
            code="unknown_jurisdiction",
            context={"jurisdiction_ids": sorted(str(i) for i in missing)},
        )
    statement = select(Jurisdiction.id).where(
        or_(*(col(Jurisdiction.path).startswith(r.path) for r in roots)),
        ~col(Jurisdiction.is_structural),
    )
    return set(session.exec(statement).all())


@dataclass(frozen=True)
class SelectionOwner:
    """Whose opt-ins: a company's, or a user's within their company."""

    kind: Literal["company", "user"]
    id: uuid.UUID
    company_id: uuid.UUID

    @classmethod
    def of_company(cls, company_id: uuid.UUID) -> SelectionOwner:
        return cls("company", company_id, company_id)

    @classmethod
    def of_user(cls, user: User) -> SelectionOwner:
        return cls("user", user.id, user.company_id)

    def etag(self, version: int) -> str:
        return f'W/"{self.kind[0]}-{self.id}-{version}"'


def _owner_table(owner: SelectionOwner) -> type[Company] | type[User]:
    return Company if owner.kind == "company" else User


def get_selection_version(*, session: Session, owner: SelectionOwner) -> int:
    table = _owner_table(owner)
    version = session.exec(
        select(table.jurisdictions_version).where(table.id == owner.id)
    ).first()
    if version is None:
        raise NotFound(
            f"{owner.kind.capitalize()} not found", code=f"{owner.kind}_not_found"
        )
    return version


def _selected_ids(*, session: Session, owner: SelectionOwner) -> set[uuid.UUID]:
    if owner.kind == "company":
        statement = select(CompanyJurisdiction.jurisdiction_id).where(
            CompanyJurisdiction.company_id == owner.id
        )
    else:
        statement = select(UserJurisdiction.jurisdiction_id).where(
            UserJurisdiction.user_id == owner.id
        )
    return set(session.exec(statement).all())


def _in_display_order(*, session: Session, ids: set[uuid.UUID]) -> list[uuid.UUID]:
    if not ids:
        return []
    statement = (
        select(Jurisdiction.id)
        .where(col(Jurisdiction.id).in_(ids))
        .order_by(col(Jurisdiction.name_path))
    )
    return list(session.exec(statement).all())


def get_selection(
    *, session: Session, owner: SelectionOwner
) -> JurisdictionSelectionOut:
    """The owner's opt-ins, ordered by name path, and the version they're at."""
    version = get_selection_version(session=session, owner=owner)
    ids = _in_display_order(
        session=session, ids=_selected_ids(session=session, owner=owner)
    )
    return JurisdictionSelectionOut(
        jurisdiction_ids=ids, count=len(ids), version=version
    )


def _bump_version(
    *, session: Session, owner: SelectionOwner, expected: int | None
) -> None:
    """Compare-and-swap the owner's version inside the write transaction, so of two
    writes from the same snapshot only the first lands. None bumps unconditionally.
    The UPDATE also takes SQLite's write lock before the current ids are read."""
    table = _owner_table(owner)
    statement = (
        update(table)
        .where(col(table.id) == owner.id)
        .values(jurisdictions_version=table.jurisdictions_version + 1)
    )
    if expected is not None:
        statement = statement.where(col(table.jurisdictions_version) == expected)
    result = session.exec(statement)
    if result.rowcount != 1:
        session.rollback()
        current = get_selection_version(session=session, owner=owner)
        raise PreconditionFailed(
            "The selection changed since you loaded it",
            context={"version": current},
        )


def _bump_user_versions(*, session: Session, user_ids: Any) -> None:
    session.exec(
        update(User)
        .where(col(User.id).in_(user_ids))
        .values(jurisdictions_version=User.jurisdictions_version + 1)
    )


def _write_selection(
    *, session: Session, owner: SelectionOwner, wanted: set[uuid.UUID]
) -> None:
    _validate_selectable(session=session, ids=wanted)
    if owner.kind == "user":
        licensed = _selected_ids(
            session=session, owner=SelectionOwner.of_company(owner.company_id)
        )
        if outside := wanted - licensed:
            raise InvalidInput(
                "The company has not opted into these jurisdictions",
                code="jurisdiction_not_licensed",
                context={"jurisdiction_ids": sorted(str(i) for i in outside)},
            )
    current = _selected_ids(session=session, owner=owner)
    removed, added = current - wanted, wanted - current
    if owner.kind == "company":
        if removed:
            # The FK cascade drops users' opt-ins without touching their versions
            _bump_user_versions(
                session=session,
                user_ids=select(UserJurisdiction.user_id).where(
                    col(UserJurisdiction.company_id) == owner.id,
                    col(UserJurisdiction.jurisdiction_id).in_(removed),
                ),
            )
            session.exec(
                delete(CompanyJurisdiction).where(
                    col(CompanyJurisdiction.company_id) == owner.id,
                    col(CompanyJurisdiction.jurisdiction_id).in_(removed),
                )
            )
        for jurisdiction_id in added:
            session.add(
                CompanyJurisdiction(
                    company_id=owner.id, jurisdiction_id=jurisdiction_id
                )
            )
        return
    if removed:
        session.exec(
            delete(UserJurisdiction).where(
                col(UserJurisdiction.user_id) == owner.id,
                col(UserJurisdiction.jurisdiction_id).in_(removed),
            )
        )
    for jurisdiction_id in added:
        session.add(
            UserJurisdiction(
                user_id=owner.id,
                company_id=owner.company_id,
                jurisdiction_id=jurisdiction_id,
            )
        )


def apply_selection(
    *,
    session: Session,
    owner: SelectionOwner,
    wanted: Iterable[uuid.UUID],
    expected_version: int | None,
) -> JurisdictionSelectionOut:
    """Replace the owner's opt-ins with `wanted`. A company's removed ids cascade to
    its users' opt-ins and bump those users' versions."""
    try:
        _bump_version(session=session, owner=owner, expected=expected_version)
        _write_selection(session=session, owner=owner, wanted=set(wanted))
    except Exception:
        session.rollback()
        raise
    session.commit()
    return get_selection(session=session, owner=owner)


def resolve_change(
    *, session: Session, owner: SelectionOwner, change: SelectionChange
) -> set[uuid.UUID]:
    """The opt-ins after the change: current, plus adds, minus removes. A user's
    add_subtrees skips what the company hasn't licensed; an explicit add doesn't."""
    pairs = [
        (change.add, change.remove),
        (change.add_subtrees, change.remove_subtrees),
    ]
    for add, remove in pairs:
        if both := set(add) & set(remove):
            raise InvalidInput(
                "Ids can't be both added and removed",
                code="selection_conflict",
                context={"jurisdiction_ids": sorted(str(i) for i in both)},
            )
    add_subtrees = get_subtree_ids(session=session, root_ids=change.add_subtrees)
    if owner.kind == "user":
        add_subtrees &= _selected_ids(
            session=session, owner=SelectionOwner.of_company(owner.company_id)
        )
    remove_subtrees = get_subtree_ids(session=session, root_ids=change.remove_subtrees)
    current = _selected_ids(session=session, owner=owner)
    return (
        (current | set(change.add) | add_subtrees)
        - set(change.remove)
        - remove_subtrees
    )


def apply_change(
    *,
    session: Session,
    owner: SelectionOwner,
    change: SelectionChange,
    expected_version: int | None,
) -> JurisdictionSelectionOut:
    """Merge a change into the owner's opt-ins. The version is bumped before the
    current ids are read, so concurrent changes apply one after the other."""
    try:
        _bump_version(session=session, owner=owner, expected=expected_version)
        wanted = resolve_change(session=session, owner=owner, change=change)
        _write_selection(session=session, owner=owner, wanted=wanted)
    except Exception:
        session.rollback()
        raise
    session.commit()
    return get_selection(session=session, owner=owner)


def preview_company_change(
    *, session: Session, company_id: uuid.UUID, change: SelectionChange
) -> SelectionPreview:
    """What apply_change would do to the company's opt-ins, and who'd lose one.
    Nothing is written."""
    owner = SelectionOwner.of_company(company_id)
    version = get_selection_version(session=session, owner=owner)
    current = _selected_ids(session=session, owner=owner)
    wanted = resolve_change(session=session, owner=owner, change=change)
    added, removed = wanted - current, current - wanted
    _validate_selectable(session=session, ids=added)
    rows = get_company_jurisdiction_affected_users(
        session=session, company_id=company_id, jurisdiction_ids=removed
    )
    return SelectionPreview(
        version=version,
        added=_in_display_order(session=session, ids=added),
        removed=_in_display_order(session=session, ids=removed),
        affected_users=JurisdictionAffectedUsers(
            data=[
                JurisdictionAffectedUser(
                    id=u.id, email=u.email, full_name=u.full_name, jurisdiction_count=n
                )
                for u, n in rows
            ],
            count=len(rows),
        ),
    )
