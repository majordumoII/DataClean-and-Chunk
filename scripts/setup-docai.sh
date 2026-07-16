#!/usr/bin/env bash
set -euo pipefail

# Script: setup-docai.sh
# Purpose: Enable Document AI API and create a Layout Parser processor
# Usage:   ./scripts/setup-docai.sh

PROJECT_ID=$(gcloud config get project)
LOCATION="us"  # or "eu"
DISPLAY_NAME="corporate-raw-docs-parser"
PROCESSOR_TYPE="LAYOUT_PARSER_PROCESSOR"

echo "Project: $PROJECT_ID"
echo "Location: $LOCATION"

# 1. Enable the API
echo "=== Enabling Document AI API ==="
gcloud services enable documentai.googleapis.com

# 2. Create the Layout Parser processor
echo "=== Creating Layout Parser processor: $DISPLAY_NAME ==="
curl -sf -X POST \
  -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  -H "Content-Type: application/json" \
  -d "{
    \"type\": \"$PROCESSOR_TYPE\",
    \"displayName\": \"$DISPLAY_NAME\"
  }" \
  "https://${LOCATION}-documentai.googleapis.com/v1/projects/${PROJECT_ID}/locations/${LOCATION}/processors" | tee /dev/stderr

echo ""
echo "Done! Save the PROCESSOR_ID from the response above."
