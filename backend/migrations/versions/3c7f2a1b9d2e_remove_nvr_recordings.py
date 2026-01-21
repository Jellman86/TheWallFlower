"""remove_nvr_recordings

Revision ID: 3c7f2a1b9d2e
Revises: efc7653464cf
Create Date: 2026-01-03
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = "3c7f2a1b9d2e"
down_revision = "efc7653464cf"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    existing_tables = set(inspector.get_table_names())
    if "recordings" in existing_tables:
        for index_name in ["ix_recordings_stream_id", "ix_recordings_start_time", "ix_recordings_end_time"]:
            try:
                op.drop_index(index_name, table_name="recordings")
            except Exception:
                pass
        op.drop_table("recordings")

    columns = {col["name"] for col in inspector.get_columns("stream_configs")}
    with op.batch_alter_table("stream_configs") as batch_op:
        if "recording_enabled" in columns:
            batch_op.drop_column("recording_enabled")
        if "recording_retention_days" in columns:
            batch_op.drop_column("recording_retention_days")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("stream_configs")}

    with op.batch_alter_table("stream_configs") as batch_op:
        if "recording_enabled" not in columns:
            batch_op.add_column(sa.Column("recording_enabled", sa.Boolean(), nullable=False, server_default="0"))
        if "recording_retention_days" not in columns:
            batch_op.add_column(sa.Column("recording_retention_days", sa.Integer(), nullable=False, server_default="7"))

    existing_tables = set(inspector.get_table_names())
    if "recordings" not in existing_tables:
        op.create_table(
            "recordings",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("stream_id", sa.Integer(), sa.ForeignKey("stream_configs.id"), nullable=False),
            sa.Column("start_time", sa.DateTime(), nullable=False),
            sa.Column("end_time", sa.DateTime(), nullable=False),
            sa.Column("duration_seconds", sa.Float(), nullable=False),
            sa.Column("file_path", sa.String(), nullable=False, unique=True),
            sa.Column("file_size_bytes", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("retention_locked", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_recordings_stream_id", "recordings", ["stream_id"], unique=False)
        op.create_index("ix_recordings_start_time", "recordings", ["start_time"], unique=False)
        op.create_index("ix_recordings_end_time", "recordings", ["end_time"], unique=False)
