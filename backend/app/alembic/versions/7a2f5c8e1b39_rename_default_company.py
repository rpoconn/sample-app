"""Rename default company to [Company Name]

Revision ID: 7a2f5c8e1b39
Revises: 4c8e2d1f9a63
Create Date: 2026-10-07 00:00:00.000000

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '7a2f5c8e1b39'
down_revision = '4c8e2d1f9a63'
branch_labels = None
depends_on = None


def upgrade():
    # Company names are unique, so skip if the new name is already taken
    op.execute(
        "UPDATE company SET name = '[Company Name]' WHERE name = 'Default' "
        "AND NOT EXISTS (SELECT 1 FROM company WHERE name = '[Company Name]')"
    )


def downgrade():
    op.execute(
        "UPDATE company SET name = 'Default' WHERE name = '[Company Name]' "
        "AND NOT EXISTS (SELECT 1 FROM company WHERE name = 'Default')"
    )
