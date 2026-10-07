"""add company and jurisdiction optins

Revision ID: dda95f2264c7
Revises: 6f40065b7e91
Create Date: 2026-10-07 13:33:39.908362

"""
import uuid
from datetime import UTC, datetime

from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = 'dda95f2264c7'
down_revision = '6f40065b7e91'
branch_labels = None
depends_on = None


# Matches app.models.DEFAULT_COMPANY_ID; existing users are moved into this company
DEFAULT_COMPANY_ID = uuid.UUID("00000000-0000-4000-8000-000000000001")


def upgrade():
    company = op.create_table('company',
    sa.Column('name', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sqlmodel.sql.sqltypes.UTCDateTime(), nullable=True),
    sa.Column('updated_at', sqlmodel.sql.sqltypes.UTCDateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('company', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_company_name'), ['name'], unique=True)

    now = datetime.now(UTC)
    op.bulk_insert(company, [{
        'id': DEFAULT_COMPANY_ID, 'name': 'Default', 'is_active': True,
        'created_at': now, 'updated_at': now,
    }])

    # Add as nullable, backfill, then tighten so existing users survive the upgrade
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('company_id', sa.Uuid(), nullable=True))
        batch_op.add_column(sa.Column('company_role', sa.String(length=20), nullable=True))

    user = sa.table('user',
        sa.column('company_id', sa.Uuid()),
        sa.column('company_role', sa.String()),
        sa.column('is_superuser', sa.Boolean()),
    )
    op.execute(user.update().values(company_id=DEFAULT_COMPANY_ID, company_role='member'))
    op.execute(user.update().where(user.c.is_superuser.is_(True)).values(company_role='admin'))

    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.alter_column('company_id', existing_type=sa.Uuid(), nullable=False)
        batch_op.alter_column('company_role', existing_type=sa.String(length=20), nullable=False)
        batch_op.create_index(batch_op.f('ix_user_company_id'), ['company_id'], unique=False)
        batch_op.create_unique_constraint('uq_user_id_company', ['id', 'company_id'])
        batch_op.create_check_constraint('ck_user_company_role', "company_role IN ('member', 'admin')")
        batch_op.create_foreign_key('fk_user_company_id_company', 'company', ['company_id'], ['id'], ondelete='RESTRICT')

    op.create_table('companyjurisdiction',
    sa.Column('company_id', sa.Uuid(), nullable=False),
    sa.Column('jurisdiction_id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sqlmodel.sql.sqltypes.UTCDateTime(), nullable=True),
    sa.ForeignKeyConstraint(['company_id'], ['company.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['jurisdiction_id'], ['jurisdiction.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('company_id', 'jurisdiction_id')
    )
    with op.batch_alter_table('companyjurisdiction', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_companyjurisdiction_jurisdiction_id'), ['jurisdiction_id'], unique=False)

    op.create_table('userjurisdiction',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('jurisdiction_id', sa.Uuid(), nullable=False),
    sa.Column('company_id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sqlmodel.sql.sqltypes.UTCDateTime(), nullable=True),
    sa.ForeignKeyConstraint(['company_id', 'jurisdiction_id'], ['companyjurisdiction.company_id', 'companyjurisdiction.jurisdiction_id'], name='fk_userjurisdiction_company_optin', ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id', 'company_id'], ['user.id', 'user.company_id'], name='fk_userjurisdiction_user_company', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id', 'jurisdiction_id')
    )
    with op.batch_alter_table('userjurisdiction', schema=None) as batch_op:
        batch_op.create_index('ix_userjurisdiction_company_jurisdiction', ['company_id', 'jurisdiction_id'], unique=False)


def downgrade():
    with op.batch_alter_table('userjurisdiction', schema=None) as batch_op:
        batch_op.drop_index('ix_userjurisdiction_company_jurisdiction')

    op.drop_table('userjurisdiction')
    with op.batch_alter_table('companyjurisdiction', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_companyjurisdiction_jurisdiction_id'))

    op.drop_table('companyjurisdiction')

    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_constraint('fk_user_company_id_company', type_='foreignkey')
        batch_op.drop_constraint('ck_user_company_role', type_='check')
        batch_op.drop_constraint('uq_user_id_company', type_='unique')
        batch_op.drop_index(batch_op.f('ix_user_company_id'))
        batch_op.drop_column('company_role')
        batch_op.drop_column('company_id')

    with op.batch_alter_table('company', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_company_name'))

    op.drop_table('company')
