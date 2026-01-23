"""add user memory tables

Revision ID: 8ebda4843d2b
Revises: d13707c1e05b
Create Date: 2026-01-15 19:26:28.074053

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8ebda4843d2b'
down_revision: Union[str, None] = 'd13707c1e05b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EMBED_DIM = 1536  # TODO: set to your embeddings dimension


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    op.execute("""
    CREATE TABLE IF NOT EXISTS moodflow_chat_messages (
      id BIGSERIAL PRIMARY KEY,
      user_id BIGINT NOT NULL,
      role TEXT NOT NULL CHECK (role IN ('user','assistant','system')),
      text TEXT NOT NULL,
      ts TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    """)

    op.execute("""
    CREATE INDEX IF NOT EXISTS moodflow_chat_messages_user_ts_idx
      ON moodflow_chat_messages(user_id, ts DESC);
    """)

    op.execute("""
    CREATE TABLE IF NOT EXISTS moodflow_user_profiles (
      user_id BIGINT PRIMARY KEY,
      profile JSONB NOT NULL DEFAULT '{}'::jsonb,
      updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    """)

    op.execute(f"""
    CREATE TABLE IF NOT EXISTS moodflow_user_memories (
      id UUID PRIMARY KEY,
      user_id BIGINT NOT NULL,
      type TEXT NOT NULL,              -- 'fact' | 'preference' | 'episode' | 'project'
      text TEXT NOT NULL,
      embedding vector({EMBED_DIM}) NOT NULL,
      importance REAL NOT NULL DEFAULT 0.5,
      is_active BOOLEAN NOT NULL DEFAULT true,
      ts TIMESTAMPTZ NOT NULL DEFAULT now(),
      text_hash TEXT NULL
    );
    """)

    op.execute("""
    CREATE INDEX IF NOT EXISTS moodflow_user_memories_user_idx
      ON moodflow_user_memories(user_id);
    """)

    op.execute("""
    CREATE INDEX IF NOT EXISTS moodflow_user_memories_user_type_idx
      ON moodflow_user_memories(user_id, type)
      WHERE is_active = true;
    """)

    # Prefer HNSW when available; otherwise you can add an IVFFlat index in a separate migration.
    op.execute("""
    DO $$
    BEGIN
      BEGIN
        EXECUTE 'CREATE INDEX IF NOT EXISTS moodflow_user_memories_hnsw_idx
                 ON moodflow_user_memories USING hnsw (embedding vector_cosine_ops)
                 WITH (m = 16, ef_construction = 128);';
      EXCEPTION WHEN others THEN
        NULL;
      END;
    END $$;
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS moodflow_user_memories;")
    op.execute("DROP TABLE IF EXISTS moodflow_user_profiles;")
    op.execute("DROP TABLE IF EXISTS moodflow_chat_messages;")
