"""Add auth_version to user, so a password change revokes older tokens

Revision ID: c7e4a2d9f163
Revises: 8b3d6f2a1c45
Create Date: 2026-10-08 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c7e4a2d9f163'
down_revision = '8b3d6f2a1c45'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                'auth_version',
                sa.Integer(),
                nullable=False,
                server_default='0',
            )
        )


def downgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('auth_version')
