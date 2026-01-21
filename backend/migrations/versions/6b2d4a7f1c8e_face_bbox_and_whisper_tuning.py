"""face_bbox_and_whisper_tuning

Revision ID: 6b2d4a7f1c8e
Revises: 3c7f2a1b9d2e
Create Date: 2026-01-03
"""

from alembic import op
import sqlalchemy as sa


revision = "6b2d4a7f1c8e"
down_revision = "3c7f2a1b9d2e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("stream_configs") as batch_op:
        batch_op.add_column(sa.Column("whisper_beam_size", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("whisper_temperature", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("whisper_no_speech_threshold", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("whisper_logprob_threshold", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("whisper_condition_on_previous_text", sa.Boolean(), nullable=True))

    with op.batch_alter_table("face_events") as batch_op:
        batch_op.add_column(sa.Column("bbox_x1", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("bbox_y1", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("bbox_x2", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("bbox_y2", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("frame_width", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("frame_height", sa.Integer(), nullable=True))

    with op.batch_alter_table("tuning_samples") as batch_op:
        batch_op.add_column(sa.Column("stream_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_tuning_samples_stream_id_stream_configs",
            "stream_configs",
            ["stream_id"],
            ["id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("tuning_samples") as batch_op:
        batch_op.drop_constraint("fk_tuning_samples_stream_id_stream_configs", type_="foreignkey")
        batch_op.drop_column("stream_id")

    with op.batch_alter_table("face_events") as batch_op:
        batch_op.drop_column("frame_height")
        batch_op.drop_column("frame_width")
        batch_op.drop_column("bbox_y2")
        batch_op.drop_column("bbox_x2")
        batch_op.drop_column("bbox_y1")
        batch_op.drop_column("bbox_x1")

    with op.batch_alter_table("stream_configs") as batch_op:
        batch_op.drop_column("whisper_condition_on_previous_text")
        batch_op.drop_column("whisper_logprob_threshold")
        batch_op.drop_column("whisper_no_speech_threshold")
        batch_op.drop_column("whisper_temperature")
        batch_op.drop_column("whisper_beam_size")
