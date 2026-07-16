"""Airflow DAG — scheduled document processing pipeline with retries and dead-letter queue.

Runs on a configurable schedule, scans the input GCS bucket for unprocessed PDFs,
runs the full pipeline (extract → clean → chunk → embed → store), and tracks
processed files to avoid re-processing. Failed files land in a dead-letter bucket.

Deploy this file to your Cloud Composer environment's dags/ folder.
"""

import json
import logging
import os
from datetime import timedelta
from typing import Any

import pendulum
from airflow import DAG
from airflow.decorators import task
from airflow.models import Variable
from google.cloud import storage as gcs

# ── Default args ──────────────────────────────────────────────────────────────

DEFAULT_ARGS = {
    "owner": "data-clean-and-chunk",
    "depends_on_past": False,
    "email_on_failure": True,
    "email_on_retry": False,
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
    "retry_exponential_backoff": True,
    "max_retry_delay": timedelta(hours=1),
    "execution_timeout": timedelta(minutes=10),
}

# ── Config (set these as Airflow Variables or fall back to env) ───────────────

def _get_config() -> dict[str, Any]:
    """Read config from Airflow Variables with env fallback."""
    defaults = {
        "input_bucket": "corporate-raw-docs",
        "output_bucket": "corporate-processed-docs",
        "dead_letter_bucket": "corporate-dlq",
        "processed_index_blob": "_pipeline/processed_files.json",
        "max_files_per_run": 50,
        "chunk_size": 1024,
        "chunk_overlap": 200,
        "embedding_model": "text-embedding-005",
        "embedding_dimensions": 768,
    }
    config = {}
    for key, default in defaults.items():
        var_name = f"PIPELINE_{key.upper()}"
        try:
            config[key] = Variable.get(var_name, default)
        except Exception:
            config[key] = os.getenv(var_name, default)
    return config


# ── Helper: track processed files in GCS ─────────────────────────────────────

def _read_processed_index(bucket: Any, blob_path: str) -> set[str]:
    """Read the set of already-processed GCS URIs from the index file."""
    try:
        blob = bucket.blob(blob_path)
        raw = blob.download_as_text()
        return set(json.loads(raw))
    except Exception:
        return set()


def _write_processed_index(bucket: Any, blob_path: str, processed: set[str]) -> None:
    """Persist the set of processed GCS URIs."""
    blob = bucket.blob(blob_path)
    blob.upload_from_string(
        json.dumps(sorted(processed)), content_type="application/json"
    )


# ── DAG definition ───────────────────────────────────────────────────────────

with DAG(
    dag_id="document_pipeline",
    default_args=DEFAULT_ARGS,
    description="Extract, clean, chunk, embed, and store corporate documents",
    schedule=os.getenv("DAG_SCHEDULE", "0 */6 * * *"),  # every 6 hours
    start_date=pendulum.today("UTC").add(days=-1),
    catchup=False,
    tags=["documents", "pipeline", "rag"],
    doc_md=__doc__,
) as dag:

    @task
    def discover_files(**context: Any) -> list[dict]:
        """List unprocessed PDFs in the input bucket and mark for processing."""
        config = _get_config()
        client = gcs.Client()
        input_bucket = client.bucket(config["input_bucket"])
        dlq_bucket = client.bucket(config["dead_letter_bucket"])

        # Ensure DLQ bucket exists
        if not dlq_bucket.exists():
            client.create_bucket(config["dead_letter_bucket"])

        # Read already-processed index
        processed = _read_processed_index(
            input_bucket, config["processed_index_blob"]
        )
        logging.info("Found %d previously processed files", len(processed))

        # Discover new PDFs
        blobs = list(input_bucket.list_blobs())
        pdfs = [
            b for b in blobs
            if b.name.lower().endswith(".pdf")
            and not b.name.startswith("_pipeline/")
        ]

        pending = []
        for blob in pdfs:
            gcs_uri = f"gs://{config['input_bucket']}/{blob.name}"
            if gcs_uri not in processed:
                pending.append({
                    "gcs_uri": gcs_uri,
                    "filename": blob.name,
                    "size": blob.size or 0,
                    "updated": blob.updated.isoformat() if blob.updated else "",
                })

        # Limit batch size
        pending = pending[: int(config["max_files_per_run"])]
        logging.info(
            "Discovered %d pending files (processing %d this run)",
            len([b for b in pdfs if f"gs://{config['input_bucket']}/{b.name}" not in processed]),
            len(pending),
        )

        # Push context for downstream tasks
        context["ti"].xcom_push(key="processed_set", value=list(processed))
        context["ti"].xcom_push(key="pending_files", value=pending)
        return pending

    @task
    def process_file(file_info: dict) -> dict:
        """Run the full pipeline on a single PDF."""
        from src.pipeline import Embedder, VectorStore
        from src.pipeline.config import PipelineConfig
        from src.pipeline.runner import PipelineRunner

        config = PipelineConfig.from_env()
        runner = PipelineRunner(config)
        embedder = Embedder(config)
        store = VectorStore(config)

        gcs_uri = file_info["gcs_uri"]
        logging.info("Processing %s ...", gcs_uri)

        try:
            # Step 1-4: Extract → Clean → Chunk → Metadata
            result = runner.process_file(gcs_uri)

            # Upload result JSON to output bucket
            output_path = runner._upload_result(result)

            # Step 5-6: Embed → Store in pgvector
            store.ensure_table()
            chunks = result["langchain_chunks"]
            texts = [c["content"] for c in chunks]
            embeddings = embedder.embed_batch(texts)
            meta = result.get("metadata", {})
            store.store_chunks(
                source=result["source"],
                filename=result["filename"],
                chunks=chunks,
                embeddings=embeddings,
                metadata=meta,
            )
            store.close()

            return {
                "status": "success",
                "gcs_uri": gcs_uri,
                "output_path": output_path,
                "chunk_count": len(chunks),
                "filename": result["filename"],
            }

        except Exception as exc:
            logging.error("Failed to process %s: %s", gcs_uri, exc)
            store.close()
            return {
                "status": "failed",
                "gcs_uri": gcs_uri,
                "filename": file_info["filename"],
                "error": str(exc),
            }

    @task
    def handle_results(
        results: list[dict],
        **context: Any,
    ) -> None:
        """Update processed index and move failures to dead-letter queue."""
        config = _get_config()
        client = gcs.Client()
        input_bucket = client.bucket(config["input_bucket"])
        dlq_bucket = client.bucket(config["dead_letter_bucket"])

        # Get current processed set from xcom
        processed = set(
            context["ti"].xcom_pull(
                key="processed_set", task_ids="discover_files"
            ) or []
        )

        successes = []
        failures = []

        for r in results:
            if r["status"] == "success":
                successes.append(r["gcs_uri"])
            else:
                failures.append(r)

        # Add successful files to the processed index
        processed.update(successes)
        _write_processed_index(
            input_bucket, config["processed_index_blob"], processed
        )
        logging.info(
            "Updated processed index: %d total files processed",
            len(processed),
        )

        # Move failed files to dead-letter queue
        for f in failures:
            dlq_blob_path = f"failed/{f['filename']}.error.json"
            dlq_blob = dlq_bucket.blob(dlq_blob_path)
            dlq_blob.upload_from_string(
                json.dumps(f, indent=2), content_type="application/json"
            )
            logging.warning("Moved %s to dead-letter queue", f["gcs_uri"])

        # Summary
        total = len(results)
        passed = len(successes)
        failed = len(failures)
        logging.info(
            "Run complete: %d/%d succeeded, %d/%d failed",
            passed,
            total,
            failed,
            total,
        )

        if failures:
            # Raise so Airflow marks the DAG as failed for alerting
            failed_files = [f["filename"] for f in failures]
            raise RuntimeError(
                f"{len(failures)} file(s) failed processing: {failed_files}"
            )

    # ── Task flow ─────────────────────────────────────────────────────────
    pending_files = discover_files()

    # Use dynamic task mapping to process each file in parallel
    # (requires Airflow 2.3+ with Cloud Composer 2+)
    processed_files = process_file.expand(file_info=pending_files)

    handle_results(processed_files)
