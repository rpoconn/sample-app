"""Lowercase user emails, so lookups and the unique index ignore case

Revision ID: 8b3d6f2a1c45
Revises: 5e8a1c3d7b90
Create Date: 2026-10-08 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8b3d6f2a1c45'
down_revision = '5e8a1c3d7b90'
branch_labels = None
depends_on = None


def upgrade():
    collisions = op.get_bind().execute(
        sa.text(
            'SELECT lower(email) FROM "user" '
            'GROUP BY lower(email) HAVING count(*) > 1'
        )
    ).scalars().all()
    if collisions:
        raise RuntimeError(
            "Merge or rename the users whose emails differ only in case, "
            f"then migrate again: {', '.join(collisions)}"
        )
    op.execute('UPDATE "user" SET email = lower(email)')


def downgrade():
    # The original casing isn't recorded, and lowercase emails stay valid
    pass
