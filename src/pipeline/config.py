import os
from dataclasses import dataclass, field


@dataclass
class PipelineConfig:
    project_id: str = field(
        default_factory=lambda: os.getenv("GOOGLE_CLOUD_PROJECT", "")
    )
    location: str = field(default_factory=lambda: os.getenv("DOCAI_LOCATION", "us"))
    processor_id: str = field(
        default_factory=lambda: os.getenv("DOCAI_PROCESSOR_ID", "")
    )
    input_bucket: str = field(
        default_factory=lambda: os.getenv("INPUT_BUCKET", "corporate-raw-docs")
    )
    output_bucket: str = field(
        default_factory=lambda: os.getenv("OUTPUT_BUCKET", "corporate-processed-docs")
    )
    chunk_size: int = field(
        default_factory=lambda: int(os.getenv("CHUNK_SIZE", "1024"))
    )
    chunk_overlap: int = field(
        default_factory=lambda: int(os.getenv("CHUNK_OVERLAP", "200"))
    )
    embedding_model_name: str = field(
        default_factory=lambda: os.getenv("EMBEDDING_MODEL", "text-embedding-005")
    )
    embedding_dimensions: int = field(
        default_factory=lambda: int(os.getenv("EMBEDDING_DIMENSIONS", "768"))
    )
    embedding_location: str = field(
        default_factory=lambda: os.getenv("EMBEDDING_LOCATION", "us-east1")
    )
    pg_connection_string: str = field(
        default_factory=lambda: os.getenv("PG_CONNECTION_STRING", "")
    )
    vector_table: str = field(
        default_factory=lambda: os.getenv("VECTOR_TABLE", "document_chunks")
    )
    # Cloud SQL instance connection name ("project:region:instance"). When
    # set, VectorStore connects via the Cloud SQL Python Connector (IAM
    # auth, no proxy/allowlisting needed) instead of pg_connection_string.
    db_instance_connection_name: str = field(
        default_factory=lambda: os.getenv("DB_INSTANCE_CONNECTION_NAME", "")
    )
    db_name: str = field(default_factory=lambda: os.getenv("DB_NAME", "docpipeline"))
    db_user: str = field(default_factory=lambda: os.getenv("DB_USER", "pipeline"))
    db_password: str = field(default_factory=lambda: os.getenv("DB_PASSWORD", ""))

    @property
    def processor_version(self) -> str:
        return "pretrained-layout-parser-v1.5-2025-08-25"

    @classmethod
    def from_env(cls) -> "PipelineConfig":
        return cls()
