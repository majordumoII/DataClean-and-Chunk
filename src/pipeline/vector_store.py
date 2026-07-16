"""pgvector storage for document chunks and their embeddings."""

import json
import logging
from typing import Any

import psycopg2
import psycopg2.extras
from pgvector.psycopg2 import register_vector

from .config import PipelineConfig

logger = logging.getLogger(__name__)

EXTENSION_DDL = "CREATE EXTENSION IF NOT EXISTS vector"

TABLE_DDL = """
CREATE TABLE IF NOT EXISTS {table} (
    id          BIGSERIAL PRIMARY KEY,
    source      TEXT NOT NULL,
    filename    TEXT NOT NULL,
    chunk_index INT  NOT NULL,
    content     TEXT NOT NULL,
    embedding   vector({dims}),
    metadata    JSONB DEFAULT '{{}}'::jsonb,
    created_at  TIMESTAMPTZ DEFAULT now()
);
"""

INDEX_DDL = """
CREATE INDEX IF NOT EXISTS idx_{table}_embedding
    ON {table} USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
"""


class VectorStore:
    """Manages pgvector storage for embedded document chunks."""

    def __init__(self, config: PipelineConfig):
        self.config = config
        self._conn: Any = None

    @property
    def conn(self):
        if self._conn is None or self._conn.closed:
            self._conn = psycopg2.connect(self.config.pg_connection_string)
            psycopg2.extras.register_uuid()
            register_vector(self._conn)
        return self._conn

    def ensure_table(self) -> None:
        """Create the vector extension, table, and index if they don't exist."""
        with self.conn.cursor() as cur:
            cur.execute(EXTENSION_DDL)
        self.conn.commit()
        with self.conn.cursor() as cur:
            cur.execute(
                TABLE_DDL.format(
                    table=self.config.vector_table,
                    dims=self.config.embedding_dimensions,
                )
            )
            try:
                cur.execute(
                    INDEX_DDL.format(table=self.config.vector_table)
                )
            except Exception:
                # index may already exist on second run
                pass
        self.conn.commit()
        logger.info("Ensured table %s exists", self.config.vector_table)

    def store_chunk(
        self,
        source: str,
        filename: str,
        chunk_index: int,
        content: str,
        embedding: list[float],
        metadata: dict | None = None,
    ) -> int:
        """Insert a single chunk with its embedding. Returns the row ID."""
        with self.conn.cursor() as cur:
            cur.execute(
                f"""
                INSERT INTO {self.config.vector_table}
                    (source, filename, chunk_index, content, embedding, metadata)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    source,
                    filename,
                    chunk_index,
                    content,
                    embedding,
                    json.dumps(metadata or {}),
                ),
            )
            row_id = cur.fetchone()[0]
        self.conn.commit()
        return row_id

    def store_chunks(
        self,
        source: str,
        filename: str,
        chunks: list[dict],
        embeddings: list[list[float]],
        metadata: dict | None = None,
    ) -> list[int]:
        """Insert multiple chunks with embeddings in one transaction."""
        if len(chunks) != len(embeddings):
            raise ValueError("chunks and embeddings must have the same length")

        rows = []
        for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
            rows.append(
                (
                    source,
                    filename,
                    chunk.get("chunk_index", i),
                    chunk["content"],
                    emb,
                    json.dumps(metadata or {}),
                )
            )

        ids: list[int] = []
        with self.conn.cursor() as cur:
            psycopg2.extras.execute_values(
                cur,
                f"""
                INSERT INTO {self.config.vector_table}
                    (source, filename, chunk_index, content, embedding, metadata)
                VALUES %s
                RETURNING id
                """,
                rows,
                template="(%s, %s, %s, %s, %s::vector, %s::jsonb)",
            )
            ids = [r[0] for r in cur.fetchall()]
        self.conn.commit()
        logger.info("Stored %d chunks in %s", len(ids), self.config.vector_table)
        return ids

    def similarity_search(
        self,
        query_embedding: list[float],
        top_k: int = 10,
    ) -> list[dict]:
        """Find the top_k most similar chunks by cosine distance."""
        with self.conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT id, source, filename, chunk_index, content, metadata,
                       1 - (embedding <=> %s::vector) AS similarity
                FROM {self.config.vector_table}
                ORDER BY embedding <=> %s::vector
                LIMIT %s
                """,
                (query_embedding, query_embedding, top_k),
            )
            rows = cur.fetchall()
        return [
            {
                "id": r[0],
                "source": r[1],
                "filename": r[2],
                "chunk_index": r[3],
                "content": r[4],
                "metadata": r[5],
                "similarity": r[6],
            }
            for r in rows
        ]

    def close(self) -> None:
        if self._conn and not self._conn.closed:
            self._conn.close()
