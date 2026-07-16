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

    @property
    def processor_version(self) -> str:
        return "pretrained-layout-parser-v1.5-2025-08-25"

    @classmethod
    def from_env(cls) -> "PipelineConfig":
        return cls()
