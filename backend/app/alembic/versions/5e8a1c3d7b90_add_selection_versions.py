"""Add selection versions to company and user, for If-Match on selection writes

Revision ID: 5e8a1c3d7b90
Revises: 9d3b6e1f4a27
Create Date: 2026-10-07 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5e8a1c3d7b90'
down_revision = '9d3b6e1f4a27'
branch_labels = None
depends_on = None


def upgrade():
    for table in ('company', 'user'):
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.add_column(
                sa.Column(
                    'jurisdictions_version',
                    sa.Integer(),
                    nullable=False,
                    server_default='0',
                )
            )


def downgrade():
    for table in ('user', 'company'):
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.drop_column('jurisdictions_version')
