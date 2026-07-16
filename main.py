"""Entry point: process documents via the pipeline."""

import argparse
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load .env before anything else
load_dotenv()

from src.pipeline import Embedder, PipelineRunner, VectorStore
from src.pipeline.config import PipelineConfig

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description="Automated Data Cleaning & Chunking Pipeline"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # Process a single file
    p_file = sub.add_parser("process", help="Process a single file from GCS")
    p_file.add_argument("gcs_uri", help="gs://bucket/path/to/file.pdf")
    p_file.add_argument("--mime-type", default="application/pdf")
    p_file.add_argument("--upload", action="store_true", help="Upload results to output bucket")
    p_file.add_argument("--store", action="store_true", help="Embed chunks and store in pgvector")

    # Batch process a prefix
    p_batch = sub.add_parser("batch", help="Process all PDFs under a GCS prefix")
    p_batch.add_argument("--prefix", default="", help="Prefix within the input bucket")
    p_batch.add_argument("--upload", action="store_true", default=True, help="Upload results (default: True)")
    p_batch.add_argument("--store", action="store_true", help="Embed and store all processed files")

    # Store an existing result JSON
    p_store = sub.add_parser("store", help="Embed and store chunks from a result JSON")
    p_store.add_argument("result_uri", help="gs://bucket/path/to/result.json or local path")

    # Search stored vectors
    p_search = sub.add_parser("search", help="Semantic search over stored document chunks")
    p_search.add_argument("query", help="Natural language query")
    p_search.add_argument("--top-k", type=int, default=10, help="Number of results (default: 10)")
    p_search.add_argument("--no-embed", action="store_true", help="Query is already an embedding vector (JSON list)")

    # Config info
    sub.add_parser("info", help="Show pipeline configuration")

    args = parser.parse_args()

    config = PipelineConfig.from_env()
    runner = PipelineRunner(config)

    def store_result(result: dict) -> None:
        """Embed and store a pipeline result's chunks into pgvector."""
        embedder = Embedder(config)
        store = VectorStore(config)
        store.ensure_table()

        chunks = result["langchain_chunks"]
        texts = [c["content"] for c in chunks]
        logger.info("Embedding %d chunks via %s ...", len(texts), config.embedding_model_name)
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
        print(f"Stored {len(chunks)} chunks in pgvector ({config.vector_table})")

    if args.command == "info":
        print("Pipeline Configuration:")
        for key, val in config.__dict__.items():
            print(f"  {key}: {val}")
        return

    if args.command == "store":
        import json as json_mod
        from tempfile import NamedTemporaryFile

        uri = args.result_uri
        if uri.startswith("gs://"):
            from google.cloud import storage as gcs

            client = gcs.Client(project=config.project_id)
            bucket_name, blob_name = uri.removeprefix("gs://").split("/", 1)
            blob = client.bucket(bucket_name).blob(blob_name)
            with NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
                blob.download_to_filename(tmp.name)
                with open(tmp.name) as f:
                    result = json_mod.load(f)
        else:
            with open(uri) as f:
                result = json_mod.load(f)
        store_result(result)
        return

    if args.command == "process":
        logger.info("Processing %s ...", args.gcs_uri)
        result = runner.process_file(args.gcs_uri, args.mime_type)
        if args.upload:
            output = runner.process_file_and_upload(args.gcs_uri, args.mime_type)
            print(f"Output: {output}")
        if args.store:
            store_result(result)
        if not args.upload and not args.store:
            # Print summary
            print(f"Source:      {result['source']}")
            print(f"Raw chars:   {result['raw_char_count']}")
            print(f"Clean chars: {result['cleaned_char_count']}")
            print(f"DocAI chunks: {result['docai_chunks_count']}")
            print(f"LangChain chunks: {result['langchain_chunks_count']}")

    elif args.command == "batch":
        if args.store:
            # Process, upload, then embed from the uploaded results
            results = runner.process_bucket_prefix_detailed(
                prefix=args.prefix, upload=args.upload
            )
            for result in results:
                store_result(result)
            print(f"\nStored {len(results)} files in pgvector")
        else:
            outputs = runner.process_bucket_prefix(prefix=args.prefix)
            print(f"\nProcessed {len(outputs)} files:")
            for o in outputs:
                print(f"  {o}")

    elif args.command == "search":
        embedder = Embedder(config)
        store = VectorStore(config)

        if args.no_embed:
            import json as json_mod
            query_vec = json_mod.loads(args.query)
        else:
            logger.info("Embedding query ...")
            query_vec = embedder.embed(args.query)

        results = store.similarity_search(query_vec, top_k=args.top_k)
        store.close()

        print(f"\nTop {len(results)} results:\n")
        for i, r in enumerate(results, 1):
            print(f"{i}. [{r['similarity']:.3f}] {r['filename']}#chunk-{r['chunk_index']}")
            print(f"   Source: {r['source']}")
            # Print first 200 chars of content
            preview = r['content'][:200].replace("\n", " ")
            print(f"   {preview}...\n" if len(r['content']) > 200 else f"   {preview}\n")


if __name__ == "__main__":
    main()
