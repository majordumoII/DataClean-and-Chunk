# Data Clean & Chunk — Automated Document Processing Pipeline

A serverless pipeline that detects new documents in Google Cloud Storage, extracts text via Document AI Layout Parser, cleans the text, splits it into semantic chunks (LangChain), and extracts metadata — ready for RAG/AI ingestion.

## Architecture

```
GCS (corporate-raw-docs)
    │
    ▼
Document AI Layout Parser    ← extracts text, tables, images
    │
    ▼
TextCleaner                  ← normalises whitespace, fixes OCR errors, removes page numbers
    │
    ▼
SemanticChunker (LangChain)  ← recursive character splitting with overlap
    │
    ▼
MetadataExtractor            ← word/line counts, table/list detection, language hint
    │
    ▼
GCS (corporate-processed-docs)  ← JSON results
    │
    ▼
Embedder (Vertex AI)           ← text-embedding-005
    │
    ▼
Vector Store (Cloud SQL pgvector)  ← cosine similarity search

┌──────────────────────────────────────────────────┐
│  Airflow DAG (scheduled, retries, DLQ)           │
│  ┌─────────┐  ┌──────────┐  ┌───────────────┐   │
│  │Discover │→ │ Process  │→ │ Handle Results│   │
│  │ Files   │  │ (map)    │  │ (index + DLQ) │   │
│  └─────────┘  └──────────┘  └───────────────┘   │
└──────────────────────────────────────────────────┘
```

## Project Structure

```
├── dags/
│   └── pipeline_dag.py         # Airflow DAG (scheduled, retries, DLQ)
├── main.py                     # CLI entry point
├── pyproject.toml              # Project config & dependencies
├── .env.example                # Environment variable template
├── scripts/
│   ├── setup-docai.sh          # Enable API + create Layout Parser processor
│   ├── setup-output-bucket.sh  # Create output bucket for results
│   ├── setup-cloudsql.sh       # Create Cloud SQL PG instance + database
│   ├── start-cloudsql-proxy.sh # Local Cloud SQL Auth Proxy
│   ├── setup-composer.sh       # Create Cloud Composer 3 environment
│   ├── process-doc.sh          # Single-file processing via curl
│   ├── batch-process.sh        # Batch processing via curl
│   └── deploy-function.sh     # Deploy Cloud Function + GCS notification
├── src/pipeline/
│   ├── __init__.py
│   ├── config.py               # PipelineConfig from env vars
│   ├── extractor.py            # DocAI Layout Parser wrapper
│   ├── cleaner.py              # Text cleaning/normalisation
│   ├── chunker.py              # LangChain semantic chunking
│   ├── metadata.py             # Metadata extraction
│   ├── embedder.py             # Vertex AI text-embedding generation
│   ├── vector_store.py         # pgvector storage + similarity search
│   ├── runner.py               # Pipeline orchestrator
│   └── event_handler.py        # Cloud Function entry point (GCS→Pub/Sub)
```

## Setup

```bash
# 1. Copy and fill in environment variables
cp .env.example .env
# Edit .env with your project ID and DOCAI_PROCESSOR_ID

# 2. Create the DocAI processor
./scripts/setup-docai.sh

# 3. Create the output bucket for results
./scripts/setup-output-bucket.sh

# 4. (Optional) Deploy Cloud Function for auto-processing
./scripts/deploy-function.sh

# 5. Manually process a single file
uv run python main.py process gs://corporate-raw-docs/sample.pdf --upload

# 6. Batch process everything already in the bucket
uv run python main.py batch --prefix ""

# 7. (Optional) Deploy Airflow DAG for scheduled processing
./scripts/setup-composer.sh
```

## Commands

| Command | Description |
|---------|-------------|
| `python main.py process <gcs_uri>` | Process one file from GCS |
| `python main.py process <gcs_uri> --upload` | Process + upload JSON result to output bucket |
| `python main.py process <gcs_uri> --store` | Process + embed chunks into pgvector |
| `python main.py process <gcs_uri> --upload --store` | Process + upload + embed all at once |
| `python main.py store <gcs_uri_or_path>` | Embed & store an already-processed result JSON |
| `python main.py search "natural language query"` | Semantic search over stored chunks |
| `python main.py search --top-k 20 "query"` | Search with more results |
| `python main.py batch --prefix ""` | Process all PDFs in the input bucket |
| `python main.py batch --prefix "" --store` | Process + embed everything |
| `python main.py info` | Show current pipeline configuration |

## Tech Stack

- **Storage:** Google Cloud Storage
- **Extraction:** Document AI Layout Parser (table + image annotations, RAG chunking)
- **Cleaning:** Custom Python (regex-based normalisation)
- **Chunking:** LangChain `RecursiveCharacterTextSplitter`
- **Metadata:** Custom extraction (word counts, table/list detection, language hints)
- **Orchestration:** Cloud Composer (Airflow DAG with retries, DLQ, scheduled runs)
- **Vector store:** Cloud SQL for PostgreSQL (pgvector extension)
- **Embeddings:** Vertex AI `text-embedding-005`
- **Deployment target:** Cloud Functions / Cloud Composer

## To-Do for Production

- [x] GCS event trigger (Pub/Sub → Cloud Function) — `scripts/deploy-function.sh`
- [x] Add chunk embeddings (Vertex AI `text-embedding-005`) — `src/pipeline/embedder.py`
- [x] Store chunks in vector DB (Cloud SQL pgvector) — `src/pipeline/vector_store.py`
- [x] Airflow DAG for scheduling & retries — `dags/pipeline_dag.py`
- [ ] Unit tests
- [ ] Error handling & dead-letter queue
