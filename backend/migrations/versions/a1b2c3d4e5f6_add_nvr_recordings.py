"""add_nvr_recordings

Revision ID: a1b2c3d4e5f6
Revises: 18f9bd9c8751
Create Date: 2026-01-01 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '18f9bd9c8751'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Get connection to check existing schema
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    # Create recordings table (if not exists)
    if 'recordings' not in existing_tables:
        op.create_table('recordings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('stream_id', sa.Integer(), nullable=False),
        sa.Column('start_time', sa.DateTime(), nullable=False),
        sa.Column('end_time', sa.DateTime(), nullable=False),
        sa.Column('duration_seconds', sa.Float(), nullable=False),
        sa.Column('file_path', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('file_size_bytes', sa.Integer(), nullable=False),
        sa.Column('retention_locked', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['stream_id'], ['stream_configs.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('file_path')
        )
        op.create_index(op.f('ix_recordings_start_time'), 'recordings', ['start_time'], unique=False)
        op.create_index(op.f('ix_recordings_end_time'), 'recordings', ['end_time'], unique=False)
        op.create_index(op.f('ix_recordings_stream_id'), 'recordings', ['stream_id'], unique=False)

    # Check existing columns in stream_configs
    existing_columns = [col['name'] for col in inspector.get_columns('stream_configs')]

    # Add columns to stream_configs (if not exist)
    # Note: SQLite doesn't support adding multiple columns in one statement easily or with server_default always behaving as expected
    # But Alembic handles it. 'server_default' is important for existing rows.
    # Boolean default=False -> 0 in SQLite
    if 'recording_enabled' not in existing_columns:
        op.add_column('stream_configs', sa.Column('recording_enabled', sa.Boolean(), nullable=False, server_default='0'))
    if 'recording_retention_days' not in existing_columns:
        op.add_column('stream_configs', sa.Column('recording_retention_days', sa.Integer(), nullable=False, server_default='7'))


def downgrade() -> None:
    # Remove columns from stream_configs
    # SQLite usually requires batch operations (recreating table) to drop columns.
    # Alembic's op.drop_column might fail on SQLite if batch mode isn't enabled in env.py.
    # Assuming batch mode is enabled or we accept that downgrade might be hard.
    # But for now we try standard ops.
    with op.batch_alter_table('stream_configs') as batch_op:
        batch_op.drop_column('recording_retention_days')
        batch_op.drop_column('recording_enabled')

    # Drop recordings table
    op.drop_index(op.f('ix_recordings_stream_id'), table_name='recordings')
    op.drop_index(op.f('ix_recordings_end_time'), table_name='recordings')
    op.drop_index(op.f('ix_recordings_start_time'), table_name='recordings')
    op.drop_table('recordings')
