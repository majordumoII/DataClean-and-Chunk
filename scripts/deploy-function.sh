#!/usr/bin/env bash
set -euo pipefail

# Script: deploy-function.sh
# Purpose: Set up GCS event notification + deploy Cloud Function for auto-processing
# Usage:   ./scripts/deploy-function.sh
#
# Prerequisites:
#   - gcloud CLI authenticated with appropriate permissions
#   - DocAI processor already created (run setup-docai.sh first)
#   - .env file populated

PROJECT_ID=$(gcloud config get project)
TOPIC_NAME="corporate-raw-docs-notify"
FUNCTION_NAME="docai-pipeline"
INPUT_BUCKET="${INPUT_BUCKET:-corporate-raw-docs}"
LOCATION="${LOCATION:-us}"

echo "Project:  $PROJECT_ID"
echo "Bucket:   $INPUT_BUCKET"
echo "Topic:    $TOPIC_NAME"
echo "Function: $FUNCTION_NAME"
echo ""

# ---- Step 1: Enable required services ----
echo "=== Enabling required APIs ==="
gcloud services enable \
    cloudfunctions.googleapis.com \
    cloudbuild.googleapis.com \
    eventarc.googleapis.com \
    pubsub.googleapis.com \
    run.googleapis.com

# ---- Step 2: Create Pub/Sub topic ----
echo "=== Creating Pub/Sub topic: $TOPIC_NAME ==="
gcloud pubsub topics create "$TOPIC_NAME" --project="$PROJECT_ID" 2>/dev/null || echo "  Topic already exists"

# ---- Step 3: Grant GCS permission to publish to the topic ----
echo "=== Granting GCS permission to publish ==="
GCS_SERVICE_ACCOUNT="service-$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')@gs-project-accounts.iam.gserviceaccount.com"
gcloud pubsub topics add-iam-policy-binding "$TOPIC_NAME" \
    --member="serviceAccount:$GCS_SERVICE_ACCOUNT" \
    --role="roles/pubsub.publisher" 2>/dev/null || echo "  Binding already exists"

# ---- Step 4: Set up GCS notification on the input bucket ----
echo "=== Setting up GCS notification on gs://$INPUT_BUCKET ==="
EXISTING=$(gcloud storage notifications list --bucket "$INPUT_BUCKET" --format="value(topic)" 2>/dev/null | grep "$TOPIC_NAME" || true)
if [ -z "$EXISTING" ]; then
    gcloud storage buckets notifications create \
        gs://"$INPUT_BUCKET" \
        --topic="$TOPIC_NAME" \
        --event-types=OBJECT_FINALIZE \
        --object-prefix="" \
        --payload-format=json
    echo "  Notification created"
else
    echo "  Notification already exists"
fi

# ---- Step 5: Export .env as .env.yaml for Cloud Function ----
echo "=== Creating .env.yaml from .env ==="
if [ ! -f .env ]; then
    echo "  ERROR: .env file not found. Copy .env.example and fill it in."
    exit 1
fi
# shellcheck disable=SC1091
source .env
cat > .env.yaml << EOF
DOCAI_LOCATION: ${DOCAI_LOCATION:-us}
DOCAI_PROCESSOR_ID: ${DOCAI_PROCESSOR_ID}
INPUT_BUCKET: ${INPUT_BUCKET:-corporate-raw-docs}
OUTPUT_BUCKET: ${OUTPUT_BUCKET:-corporate-processed-docs}
CHUNK_SIZE: ${CHUNK_SIZE:-1024}
CHUNK_OVERLAP: ${CHUNK_OVERLAP:-200}
EOF
echo "  Created .env.yaml"

# ---- Step 6: Deploy the Cloud Function ----
echo "=== Deploying Cloud Function: $FUNCTION_NAME ==="
gcloud functions deploy "$FUNCTION_NAME" \
    --runtime=python313 \
    --trigger-topic="$TOPIC_NAME" \
    --source=. \
    --entry-point=handle_gcs_event \
    --env-vars-file=.env.yaml \
    --region="$LOCATION" \
    --memory=512MB \
    --timeout=300s \
    --min-instances=0 \
    --max-instances=10

echo ""
echo "=== Done ==="
echo "New PDFs uploaded to gs://$INPUT_BUCKET/ will now be auto-processed."
echo "Check logs: gcloud functions logs read $FUNCTION_NAME --region=$LOCATION"
