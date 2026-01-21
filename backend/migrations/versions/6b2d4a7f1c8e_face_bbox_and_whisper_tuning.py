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
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if "stream_configs" in existing_tables:
        stream_config_cols = {col["name"] for col in inspector.get_columns("stream_configs")}
        with op.batch_alter_table("stream_configs") as batch_op:
            if "whisper_beam_size" not in stream_config_cols:
                batch_op.add_column(sa.Column("whisper_beam_size", sa.Integer(), nullable=True))
            if "whisper_temperature" not in stream_config_cols:
                batch_op.add_column(sa.Column("whisper_temperature", sa.String(), nullable=True))
            if "whisper_no_speech_threshold" not in stream_config_cols:
                batch_op.add_column(sa.Column("whisper_no_speech_threshold", sa.Float(), nullable=True))
            if "whisper_logprob_threshold" not in stream_config_cols:
                batch_op.add_column(sa.Column("whisper_logprob_threshold", sa.Float(), nullable=True))
            if "whisper_condition_on_previous_text" not in stream_config_cols:
                batch_op.add_column(sa.Column("whisper_condition_on_previous_text", sa.Boolean(), nullable=True))

    if "face_events" in existing_tables:
        face_event_cols = {col["name"] for col in inspector.get_columns("face_events")}
        with op.batch_alter_table("face_events") as batch_op:
            if "bbox_x1" not in face_event_cols:
                batch_op.add_column(sa.Column("bbox_x1", sa.Integer(), nullable=True))
            if "bbox_y1" not in face_event_cols:
                batch_op.add_column(sa.Column("bbox_y1", sa.Integer(), nullable=True))
            if "bbox_x2" not in face_event_cols:
                batch_op.add_column(sa.Column("bbox_x2", sa.Integer(), nullable=True))
            if "bbox_y2" not in face_event_cols:
                batch_op.add_column(sa.Column("bbox_y2", sa.Integer(), nullable=True))
            if "frame_width" not in face_event_cols:
                batch_op.add_column(sa.Column("frame_width", sa.Integer(), nullable=True))
            if "frame_height" not in face_event_cols:
                batch_op.add_column(sa.Column("frame_height", sa.Integer(), nullable=True))

    if "tuning_samples" in existing_tables:
        tuning_sample_cols = {col["name"] for col in inspector.get_columns("tuning_samples")}
        with op.batch_alter_table("tuning_samples") as batch_op:
            if "stream_id" not in tuning_sample_cols:
                batch_op.add_column(sa.Column("stream_id", sa.Integer(), nullable=True))

            existing_fks = {fk["name"] for fk in inspector.get_foreign_keys("tuning_samples")}
            if "fk_tuning_samples_stream_id_stream_configs" not in existing_fks:
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
