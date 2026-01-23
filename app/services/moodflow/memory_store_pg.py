from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from typing import Any, Literal, Optional, Sequence

from sqlalchemy import text, bindparam
from sqlalchemy.ext.asyncio import AsyncSession


MemoryType = Literal["fact", "preference", "episode", "project"]


@dataclass
class MemoryDoc:
    id: uuid.UUID
    user_id: int
    type: MemoryType
    text: str
    importance: float
    ts: str  # ISO string
    text_hash: Optional[str] = None


def _hash_text(s: str) -> str:
    norm = " ".join(s.lower().strip().split())
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


class MemoryStorePG:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def append_message(self, user_id: int, role: str, text_: str) -> None:
        await self.session.execute(
            text(
                """
                INSERT INTO moodflow_chat_messages(user_id, role, text, ts)
                VALUES (:user_id, :role, :text, now())
                """
            ),
            {"user_id": user_id, "role": role, "text": text_},
        )

    async def get_recent_history(self, user_id: int, limit: int = 20) -> list[dict[str, str]]:
        res = await self.session.execute(
            text(
                """
                SELECT role, text
                FROM moodflow_chat_messages
                WHERE user_id = :user_id
                ORDER BY ts DESC
                LIMIT :limit
                """
            ),
            {"user_id": user_id, "limit": limit},
        )
        rows = list(res.mappings().all())
        return [{"role": r["role"], "text": r["text"]} for r in reversed(rows)]

    async def get_profile(self, user_id: int) -> dict[str, Any]:
        res = await self.session.execute(
            text("SELECT profile FROM moodflow_user_profiles WHERE user_id = :user_id"),
            {"user_id": user_id},
        )
        row = res.mappings().first()
        if not row:
            await self.session.execute(
                text(
                    """
                    INSERT INTO moodflow_user_profiles(user_id, profile, updated_at)
                    VALUES (:user_id, '{}'::jsonb, now())
                    """
                ),
                {"user_id": user_id},
            )
            return {}
        return row["profile"] or {}

    async def patch_profile(self, user_id: int, patch: dict[str, Any]) -> None:
        await self.session.execute(
            text(
                """
                INSERT INTO moodflow_user_profiles(user_id, profile, updated_at)
                VALUES (:user_id, CAST(:patch AS jsonb), now())
                ON CONFLICT (user_id)
                DO UPDATE SET profile = moodflow_user_profiles.profile || EXCLUDED.profile,
                              updated_at = now()
                """
            ),
            {"user_id": user_id, "patch": json.dumps(patch)},
        )

    async def search_memories(
            self,
            *,
            user_id: int,
            query_embedding: Sequence[float],
            k: int = 10,
            types: Optional[list[str]] = None,
    ) -> list[MemoryDoc]:
        emb = "[" + ",".join(f"{x:.6f}" for x in query_embedding) + "]"

        sql_str = """
            SELECT id, user_id, type, text, importance, ts, text_hash
            FROM moodflow_user_memories
            WHERE user_id = :user_id
              AND is_active = true
        """
        if types:
            sql_str += " AND type = ANY(CAST(:types AS text[])) "

        sql_str += """
            ORDER BY embedding <=> CAST(:emb AS vector)
            LIMIT :k
        """

        stmt = text(sql_str).bindparams(
            bindparam("user_id"),
            bindparam("emb"),
            bindparam("k"),
        )

        params: dict[str, Any] = {"user_id": user_id, "emb": emb, "k": k}
        if types:
            params["types"] = types

        res = await self.session.execute(stmt, params)
        rows = res.mappings().all()

        out: list[MemoryDoc] = []
        for r in rows:
            out.append(
                MemoryDoc(
                    id=r["id"],
                    user_id=r["user_id"],
                    type=r["type"],
                    text=r["text"],
                    importance=float(r["importance"]),
                    ts=r["ts"].isoformat() if hasattr(r["ts"], "isoformat") else str(r["ts"]),
                    text_hash=r.get("text_hash"),
                )
            )
        return out

    async def upsert_memories(
        self,
        *,
        user_id: int,
        docs: list[tuple[MemoryType, str, Sequence[float], float]],
        dedup: bool = True,
    ) -> None:
        for t, txt, embedding, importance in docs:
            h = _hash_text(txt) if dedup else None
            emb = "[" + ",".join(f"{x:.6f}" for x in embedding) + "]"
            mem_id = uuid.uuid4()

            # If the same normalized text was stored before, deactivate the old one and insert a fresh version.
            if dedup and h:
                await self.session.execute(
                    text(
                        """
                        UPDATE moodflow_user_memories
                        SET is_active = false
                        WHERE user_id = :user_id AND text_hash = :h AND is_active = true
                        """
                    ),
                    {"user_id": user_id, "h": h},
                )

            await self.session.execute(
                text(
                    """
                    INSERT INTO moodflow_user_memories(id, user_id, type, text, embedding, importance, is_active, ts, text_hash)
                    VALUES (:id, :user_id, :type, :text, CAST(:emb AS vector), :importance, true, now(), :h)
                    """
                ),
                {
                    "id": str(mem_id),
                    "user_id": user_id,
                    "type": t,
                    "text": txt,
                    "emb": emb,
                    "importance": importance,
                    "h": h,
                },
            )
