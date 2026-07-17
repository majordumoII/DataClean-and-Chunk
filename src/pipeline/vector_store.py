"""pgvector storage for document chunks and their embeddings."""

import json
import logging
from typing import Any

from google.cloud.sql.connector import Connector
from pgvector import Vector

from .config import PipelineConfig

logger = logging.getLogger(__name__)


def _register_vector_dbapi(conn: Any) -> None:
    """Register pgvector in/out adapters on a pg8000 DBAPI connection.

    pgvector.pg8000.register_vector expects a pg8000.native.Connection
    (uses conn.run(...) for the type lookup); the Cloud SQL Connector and
    our local dbapi.connect() both produce pg8000.dbapi.Connection, which
    lacks .run() but does support the same register_in/out_adapter calls.
    """
    cur = conn.cursor()
    cur.execute(
        "SELECT typname, oid FROM pg_type WHERE oid IN "
        "(to_regtype('vector'), to_regtype('halfvec'), to_regtype('sparsevec'))"
    )
    type_info = dict(cur.fetchall())
    cur.close()

    if "vector" not in type_info:
        raise RuntimeError("vector type not found in the database")

    conn.register_out_adapter(Vector, lambda v: v.to_text())
    conn.register_in_adapter(type_info["vector"], Vector.from_text)


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
        self._closed = True
        self._connector: Connector | None = None

    @property
    def conn(self):
        if self._conn is None or self._closed:
            if self.config.db_instance_connection_name:
                # Cloud SQL Python Connector: IAM-authenticated, works from
                # any environment without proxy sidecars or IP allowlisting
                # (needed since Composer/Cloud Run workers have no stable
                # IPs to authorize).
                self._connector = Connector()
                self._conn = self._connector.connect(
                    self.config.db_instance_connection_name,
                    "pg8000",
                    user=self.config.db_user,
                    password=self.config.db_password,
                    db=self.config.db_name,
                )
            else:
                # Local dev: plain TCP via Cloud SQL Auth Proxy on localhost.
                from urllib.parse import urlparse

                import pg8000.dbapi as dbapi

                parsed = urlparse(self.config.pg_connection_string)
                self._conn = dbapi.connect(
                    user=parsed.username,
                    password=parsed.password,
                    host=parsed.hostname or "localhost",
                    port=parsed.port or 5432,
                    database=parsed.path.lstrip("/"),
                )
            _register_vector_dbapi(self._conn)
            self._closed = False
        return self._conn

    def ensure_table(self) -> None:
        """Create the vector extension, table, and index if they don't exist."""
        cur = self.conn.cursor()
        cur.execute(EXTENSION_DDL)
        self.conn.commit()
        cur.execute(
            TABLE_DDL.format(
                table=self.config.vector_table,
                dims=self.config.embedding_dimensions,
            )
        )
        try:
            cur.execute(INDEX_DDL.format(table=self.config.vector_table))
        except Exception:
            # index may already exist on second run
            pass
        self.conn.commit()
        cur.close()
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
        cur = self.conn.cursor()
        cur.execute(
            f"""
            INSERT INTO {self.config.vector_table}
                (source, filename, chunk_index, content, embedding, metadata)
            VALUES (%s, %s, %s, %s, %s::vector, %s::jsonb)
            RETURNING id
            """,
            (
                source,
                filename,
                chunk_index,
                content,
                Vector(embedding),
                json.dumps(metadata or {}),
            ),
        )
        row_id = cur.fetchone()[0]
        self.conn.commit()
        cur.close()
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

        cur = self.conn.cursor()
        ids: list[int] = []
        for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
            cur.execute(
                f"""
                INSERT INTO {self.config.vector_table}
                    (source, filename, chunk_index, content, embedding, metadata)
                VALUES (%s, %s, %s, %s, %s::vector, %s::jsonb)
                RETURNING id
                """,
                (
                    source,
                    filename,
                    chunk.get("chunk_index", i),
                    chunk["content"],
                    Vector(emb),
                    json.dumps(metadata or {}),
                ),
            )
            ids.append(cur.fetchone()[0])
        self.conn.commit()
        cur.close()
        logger.info("Stored %d chunks in %s", len(ids), self.config.vector_table)
        return ids

    def similarity_search(
        self,
        query_embedding: list[float],
        top_k: int = 10,
    ) -> list[dict]:
        """Find the top_k most similar chunks by cosine distance."""
        cur = self.conn.cursor()
        cur.execute(
            f"""
            SELECT id, source, filename, chunk_index, content, metadata,
                   1 - (embedding <=> %s::vector) AS similarity
            FROM {self.config.vector_table}
            ORDER BY embedding <=> %s::vector
            LIMIT %s
            """,
            (Vector(query_embedding), Vector(query_embedding), top_k),
        )
        rows = cur.fetchall()
        cur.close()
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
        if self._conn and not self._closed:
            self._conn.close()
            self._closed = True
        if self._connector is not None:
            self._connector.close()
            self._connector = None
