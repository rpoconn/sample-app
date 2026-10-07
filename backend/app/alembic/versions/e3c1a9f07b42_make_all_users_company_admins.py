"""Make all users company admins

Revision ID: e3c1a9f07b42
Revises: dda95f2264c7
Create Date: 2026-10-07 00:00:00.000000

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = 'e3c1a9f07b42'
down_revision = 'dda95f2264c7'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("UPDATE \"user\" SET company_role = 'admin'")


def downgrade():
    # Original roles aren't recorded; only superusers stay admins
    op.execute("UPDATE \"user\" SET company_role = 'member' WHERE is_superuser = 0")
