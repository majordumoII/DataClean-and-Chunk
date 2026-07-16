#!/usr/bin/env bash
set -euo pipefail

# Script: process-doc.sh
# Purpose: Process a single document through Document AI Layout Parser
# Usage:   ./scripts/process-doc.sh gs://bucket/path/to/file.pdf [mime-type]

GCS_URI="${1:?Usage: $0 gs://bucket/path/to/file.pdf [mime-type]}"
MIME_TYPE="${2:-application/pdf}"

PROJECT_ID=$(gcloud config get project)
LOCATION="us"
PROCESSOR_ID="${PROCESSOR_ID:?Set PROCESSOR_ID env var: export PROCESSOR_ID=your-processor-id}"
PROCESSOR_VERSION="pretrained-layout-parser-v1.5-2025-08-25"

echo "Project: $PROJECT_ID"
echo "File:    $GCS_URI"
echo "MIME:    $MIME_TYPE"

curl -sf -X POST \
  -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  -H "Content-Type: application/json" \
  -d "{
    \"gcsDocument\": {
      \"gcsUri\": \"$GCS_URI\",
      \"mimeType\": \"$MIME_TYPE\"
    },
    \"processOptions\": {
      \"layoutConfig\": {
        \"enableTableAnnotation\": true,
        \"enableImageAnnotation\": true,
        \"chunkingConfig\": {
          \"chunkSize\": 1024,
          \"includeAncestorHeadings\": true
        }
      }
    }
  }" \
  "https://${LOCATION}-documentai.googleapis.com/v1beta3/projects/${PROJECT_ID}/locations/${LOCATION}/processors/${PROCESSOR_ID}/processorVersions/${PROCESSOR_VERSION}:process" | jq '.document.chunked_document.chunks'
