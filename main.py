"""Entry point: process documents via the pipeline."""

import argparse
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load .env before anything else
load_dotenv()

from src.pipeline import PipelineRunner
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

    # Batch process a prefix
    p_batch = sub.add_parser("batch", help="Process all PDFs under a GCS prefix")
    p_batch.add_argument("--prefix", default="", help="Prefix within the input bucket")
    p_batch.add_argument("--upload", action="store_true", default=True, help="Upload results (default: True)")

    # Config info
    sub.add_parser("info", help="Show pipeline configuration")

    args = parser.parse_args()

    config = PipelineConfig.from_env()
    runner = PipelineRunner(config)

    if args.command == "info":
        print("Pipeline Configuration:")
        for key, val in config.__dict__.items():
            print(f"  {key}: {val}")
        return

    if args.command == "process":
        logger.info("Processing %s ...", args.gcs_uri)
        if args.upload:
            output = runner.process_file_and_upload(args.gcs_uri, args.mime_type)
            print(f"Output: {output}")
        else:
            result = runner.process_file(args.gcs_uri, args.mime_type)
            # Print summary
            print(f"Source:      {result['source']}")
            print(f"Raw chars:   {result['raw_char_count']}")
            print(f"Clean chars: {result['cleaned_char_count']}")
            print(f"DocAI chunks: {result['docai_chunks_count']}")
            print(f"LangChain chunks: {result['langchain_chunks_count']}")

    elif args.command == "batch":
        outputs = runner.process_bucket_prefix(prefix=args.prefix)
        print(f"\nProcessed {len(outputs)} files:")
        for o in outputs:
            print(f"  {o}")


if __name__ == "__main__":
    main()
