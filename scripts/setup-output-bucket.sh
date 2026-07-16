#!/usr/bin/env bash
set -euo pipefail

# Script: setup-output-bucket.sh
# Purpose: Create the output bucket for processed results
# Usage:   ./scripts/setup-output-bucket.sh

OUTPUT_BUCKET="${OUTPUT_BUCKET:-corporate-processed-docs}"
LOCATION="${LOCATION:-us}"

echo "Creating output bucket: gs://$OUTPUT_BUCKET"

gcloud storage buckets create "gs://$OUTPUT_BUCKET" \
    --location="$LOCATION" \
    --uniform-bucket-level-access 2>/dev/null \
    && echo "Created!" \
    || echo "Already exists or unable to create (bucket name must be globally unique)"
