#!/usr/bin/env bash
set -euo pipefail

# Script: batch-process.sh
# Purpose: Batch process all documents in a GCS prefix through Layout Parser
# Usage:   ./scripts/batch-process.sh gs://bucket/path/to/documents/

INPUT_PREFIX="${1:?Usage: $0 gs://bucket/path/to/documents/}"
OUTPUT_BUCKET="${2:-${INPUT_PREFIX%/}-output}"

PROJECT_ID=$(gcloud config get project)
LOCATION="us"
PROCESSOR_ID="${PROCESSOR_ID:?Set PROCESSOR_ID env var: export PROCESSOR_ID=your-processor-id}"
PROCESSOR_VERSION="pretrained-layout-parser-v1.5-2025-08-25"

echo "Input:  $INPUT_PREFIX"
echo "Output: gs://$OUTPUT_BUCKET/"

curl -sf -X POST \
  -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  -H "Content-Type: application/json" \
  -d "{
    \"inputDocuments\": {
      \"gcsDocuments\": {
        \"mimeType\": \"application/pdf\"
      },
      \"gcsPrefix\": {
        \"gcsUriPrefix\": \"$INPUT_PREFIX\"
      }
    },
    \"documentOutputConfig\": {
      \"gcsOutputConfig\": {
        \"gcsUri\": \"gs://$OUTPUT_BUCKET/\"
      }
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
  "https://${LOCATION}-documentai.googleapis.com/v1beta3/projects/${PROJECT_ID}/locations/${LOCATION}/processors/${PROCESSOR_ID}/processorVersions/${PROCESSOR_VERSION}:batchProcess"

echo ""
echo "Check operation status with:"
echo "  gcloud ai operations describe <operation-name>"
