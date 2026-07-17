"""Tests for VectorStore (with mocked pg8000 and pgvector)."""

import json
from unittest.mock import MagicMock

import pytest

from src.pipeline.vector_store import VectorStore


@pytest.fixture
def mock_conn():
    """Return a mock pg8000 dbapi connection with a plain (non-context-manager) cursor."""
    conn = MagicMock()
    cursor = MagicMock()
    cursor.fetchone.return_value = [42]
    cursor.fetchall.return_value = [(1,), (2,)]
    conn.cursor.return_value = cursor
    return conn


class TestVectorStore:
    def test_ensure_table_creates_table(self, config, mocker, mock_conn):
        mocker.patch("pg8000.dbapi.connect", return_value=mock_conn)
        mocker.patch("src.pipeline.vector_store._register_vector_dbapi")

        store = VectorStore(config)
        store.ensure_table()

        calls = mock_conn.cursor.return_value.execute.call_args_list
        extension_sql = calls[0][0][0]
        assert "CREATE EXTENSION IF NOT EXISTS vector" in extension_sql
        create_table_sql = calls[1][0][0]
        assert "CREATE TABLE IF NOT EXISTS" in create_table_sql
        assert config.vector_table in create_table_sql
        assert mock_conn.commit.called

    def test_store_chunk_returns_id(self, config, mocker, mock_conn):
        mocker.patch("pg8000.dbapi.connect", return_value=mock_conn)
        mocker.patch("src.pipeline.vector_store._register_vector_dbapi")

        store = VectorStore(config)
        row_id = store.store_chunk(
            source="gs://bucket/doc.pdf",
            filename="doc.pdf",
            chunk_index=0,
            content="Hello world.",
            embedding=[0.1, 0.2, 0.3],
            metadata={"char_count": 12},
        )

        assert row_id == 42

    def test_store_chunks_mismatch_raises(self, config, mocker):
        mocker.patch("pg8000.dbapi.connect")
        mocker.patch("src.pipeline.vector_store._register_vector_dbapi")

        store = VectorStore(config)
        with pytest.raises(ValueError, match="must have the same length"):
            store.store_chunks(
                source="gs://bucket/doc.pdf",
                filename="doc.pdf",
                chunks=[{"content": "hello", "chunk_index": 0}],
                embeddings=[[0.1], [0.2]],  # 2 embeddings, 1 chunk
            )

    def test_store_chunks_batch_insert(self, config, mocker, mock_conn):
        mock_cursor = mock_conn.cursor.return_value
        mock_cursor.fetchone.side_effect = [[1], [2]]
        mocker.patch("pg8000.dbapi.connect", return_value=mock_conn)
        mocker.patch("src.pipeline.vector_store._register_vector_dbapi")

        store = VectorStore(config)
        ids = store.store_chunks(
            source="gs://bucket/doc.pdf",
            filename="doc.pdf",
            chunks=[
                {"content": "Chunk 1", "chunk_index": 0},
                {"content": "Chunk 2", "chunk_index": 1},
            ],
            embeddings=[[0.1, 0.2], [0.3, 0.4]],
        )

        assert ids == [1, 2]

    def test_similarity_search_returns_results(self, config, mocker, mock_conn):
        mock_cursor = mock_conn.cursor.return_value
        mock_cursor.fetchall.return_value = [
            (1, "gs://b/doc.pdf", "doc.pdf", 0, "Content 1", {}, 0.95),
            (2, "gs://b/doc.pdf", "doc.pdf", 1, "Content 2", {}, 0.87),
        ]
        mocker.patch("pg8000.dbapi.connect", return_value=mock_conn)
        mocker.patch("src.pipeline.vector_store._register_vector_dbapi")

        store = VectorStore(config)
        results = store.similarity_search(
            query_embedding=[0.1, 0.2], top_k=5
        )

        assert len(results) == 2
        assert results[0]["id"] == 1
        assert results[0]["similarity"] == 0.95
        assert results[1]["id"] == 2
        assert results[1]["similarity"] == 0.87

    def test_close_connection(self, config, mocker, mock_conn):
        mocker.patch("pg8000.dbapi.connect", return_value=mock_conn)
        mocker.patch("src.pipeline.vector_store._register_vector_dbapi")

        store = VectorStore(config)
        _ = store.conn
        store.close()

        mock_conn.close.assert_called_once()

    def test_close_idempotent_when_already_closed(self, config, mocker):
        store = VectorStore(config)
        store.close()  # should not raise; conn was never opened

    def test_ensure_table_handles_existing_index(self, config, mocker, mock_conn):
        mock_cursor = mock_conn.cursor.return_value
        # Make the third execute (CREATE INDEX) raise, after extension + table DDL
        mock_cursor.execute.side_effect = [None, None, Exception("index exists")]
        mocker.patch("pg8000.dbapi.connect", return_value=mock_conn)
        mocker.patch("src.pipeline.vector_store._register_vector_dbapi")

        store = VectorStore(config)
        store.ensure_table()  # should not raise

    def test_stored_chunks_use_vector_cast(self, config, mocker, mock_conn):
        mocker.patch("pg8000.dbapi.connect", return_value=mock_conn)
        mocker.patch("src.pipeline.vector_store._register_vector_dbapi")

        store = VectorStore(config)
        store.store_chunks(
            source="gs://bucket/doc.pdf",
            filename="doc.pdf",
            chunks=[{"content": "Hello", "chunk_index": 0}],
            embeddings=[[0.1, 0.2]],
        )

        insert_call = mock_conn.cursor.return_value.execute.call_args_list[0]
        sql = insert_call[0][0]
        assert "%s::vector" in sql
        assert "%s::jsonb" in sql
