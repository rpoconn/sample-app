"""add jurisdiction code and region type

Revision ID: 4c8e2d1f9a63
Revises: e3c1a9f07b42
Create Date: 2026-10-07 00:00:00.000000

"""
import json
import uuid
from pathlib import Path

from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = '4c8e2d1f9a63'
down_revision = 'e3c1a9f07b42'
branch_labels = None
depends_on = None


SEED_FILE = Path(__file__).parents[2] / "data" / "jurisdictions.json"


def upgrade():
    with op.batch_alter_table('jurisdiction', schema=None) as batch_op:
        batch_op.add_column(sa.Column('code', sqlmodel.sql.sqltypes.AutoString(length=3), nullable=True))
        batch_op.add_column(sa.Column('region_type', sa.String(length=20), nullable=True))

    # Backfill seeded rows by their stable ids; the seed only runs on first setup
    jurisdiction = sa.table('jurisdiction',
        sa.column('id', sa.Uuid()),
        sa.column('code', sa.String()),
        sa.column('region_type', sa.String()),
    )
    bind = op.get_bind()

    def walk(nodes):
        for node in nodes:
            if node.get('code'):
                bind.execute(
                    jurisdiction.update()
                    .where(jurisdiction.c.id == uuid.UUID(node['id']))
                    .values(code=node['code'], region_type=node.get('regionType'))
                )
            walk(node.get('jurisdictions', []))

    walk(json.loads(SEED_FILE.read_text(encoding='utf-8')))


def downgrade():
    with op.batch_alter_table('jurisdiction', schema=None) as batch_op:
        batch_op.drop_column('region_type')
        batch_op.drop_column('code')
