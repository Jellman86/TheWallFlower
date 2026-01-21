"""init_schema

Revision ID: 9f2c7b1a6d3e
Revises:
Create Date: 2026-01-21
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = "9f2c7b1a6d3e"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "stream_configs",
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("rtsp_url", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("whisper_enabled", sa.Boolean(), nullable=False),
        sa.Column("face_detection_enabled", sa.Boolean(), nullable=False),
        sa.Column("face_detection_interval", sa.Integer(), nullable=False),
        sa.Column("save_transcripts_to_file", sa.Boolean(), nullable=False),
        sa.Column("transcript_file_path", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("audio_energy_threshold", sa.Float(), nullable=True),
        sa.Column("audio_vad_enabled", sa.Boolean(), nullable=True),
        sa.Column("audio_vad_threshold", sa.Float(), nullable=True),
        sa.Column("audio_vad_onset", sa.Float(), nullable=True),
        sa.Column("audio_vad_offset", sa.Float(), nullable=True),
        sa.Column("whisper_beam_size", sa.Integer(), nullable=True),
        sa.Column("whisper_temperature", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("whisper_no_speech_threshold", sa.Float(), nullable=True),
        sa.Column("whisper_logprob_threshold", sa.Float(), nullable=True),
        sa.Column("whisper_condition_on_previous_text", sa.Boolean(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_stream_configs_name"), "stream_configs", ["name"], unique=False)

    op.create_table(
        "faces",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("embedding", sa.LargeBinary(), nullable=False),
        sa.Column("thumbnail_path", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("first_seen", sa.DateTime(), nullable=False),
        sa.Column("last_seen", sa.DateTime(), nullable=False),
        sa.Column("is_known", sa.Boolean(), nullable=False),
        sa.Column("embedding_count", sa.Integer(), nullable=False),
        sa.Column("avg_embedding", sa.LargeBinary(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_faces_name"), "faces", ["name"], unique=False)

    op.create_table(
        "face_embeddings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("face_id", sa.Integer(), nullable=False),
        sa.Column("embedding", sa.LargeBinary(), nullable=False),
        sa.Column("source", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("quality_score", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("image_path", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.ForeignKeyConstraint(["face_id"], ["faces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_face_embeddings_face_id"), "face_embeddings", ["face_id"], unique=False)

    op.create_table(
        "face_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("stream_id", sa.Integer(), nullable=False),
        sa.Column("face_id", sa.Integer(), nullable=True),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("snapshot_path", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("bbox_x1", sa.Integer(), nullable=True),
        sa.Column("bbox_y1", sa.Integer(), nullable=True),
        sa.Column("bbox_x2", sa.Integer(), nullable=True),
        sa.Column("bbox_y2", sa.Integer(), nullable=True),
        sa.Column("frame_width", sa.Integer(), nullable=True),
        sa.Column("frame_height", sa.Integer(), nullable=True),
        sa.Column("face_name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.ForeignKeyConstraint(["face_id"], ["faces.id"]),
        sa.ForeignKeyConstraint(["stream_id"], ["stream_configs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_face_events_stream_id"), "face_events", ["stream_id"], unique=False)
    op.create_index(op.f("ix_face_events_timestamp"), "face_events", ["timestamp"], unique=False)

    op.create_table(
        "transcripts",
        sa.Column("stream_id", sa.Integer(), nullable=False),
        sa.Column("text", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("start_time", sa.Float(), nullable=False),
        sa.Column("end_time", sa.Float(), nullable=False),
        sa.Column("is_final", sa.Boolean(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("speaker_id", sa.Integer(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["stream_id"], ["stream_configs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_transcripts_created_at"), "transcripts", ["created_at"], unique=False)
    op.create_index(op.f("ix_transcripts_stream_id"), "transcripts", ["stream_id"], unique=False)

    op.create_table(
        "tuning_samples",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("stream_id", sa.Integer(), nullable=True),
        sa.Column("filename", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("original_transcript", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("ground_truth", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("duration_seconds", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["stream_id"], ["stream_configs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_tuning_samples_stream_id"), "tuning_samples", ["stream_id"], unique=False)

    op.create_table(
        "tuning_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("sample_id", sa.Integer(), nullable=False),
        sa.Column("beam_size", sa.Integer(), nullable=False),
        sa.Column("temperature", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("vad_threshold", sa.Float(), nullable=False),
        sa.Column("transcription", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("wer", sa.Float(), nullable=False),
        sa.Column("execution_time", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["sample_id"], ["tuning_samples.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_tuning_runs_sample_id"), "tuning_runs", ["sample_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_tuning_runs_sample_id"), table_name="tuning_runs")
    op.drop_table("tuning_runs")
    op.drop_index(op.f("ix_tuning_samples_stream_id"), table_name="tuning_samples")
    op.drop_table("tuning_samples")
    op.drop_index(op.f("ix_transcripts_stream_id"), table_name="transcripts")
    op.drop_index(op.f("ix_transcripts_created_at"), table_name="transcripts")
    op.drop_table("transcripts")
    op.drop_index(op.f("ix_face_events_timestamp"), table_name="face_events")
    op.drop_index(op.f("ix_face_events_stream_id"), table_name="face_events")
    op.drop_table("face_events")
    op.drop_index(op.f("ix_face_embeddings_face_id"), table_name="face_embeddings")
    op.drop_table("face_embeddings")
    op.drop_index(op.f("ix_faces_name"), table_name="faces")
    op.drop_table("faces")
    op.drop_index(op.f("ix_stream_configs_name"), table_name="stream_configs")
    op.drop_table("stream_configs")
