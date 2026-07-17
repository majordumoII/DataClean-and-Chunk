#!/usr/bin/env bash
set -euo pipefail

# Creates a Cloud Composer 3 environment and syncs the DAG.
# Usage: ./scripts/setup-composer.sh [environment-name] [region]

ENV_NAME="${1:-docpipeline-composer}"
REGION="${2:-us-central1}"
PROJECT_ID=$(gcloud config get project)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
SA_EMAIL="pipeline-runner@${PROJECT_ID}.iam.gserviceaccount.com"

echo "=== Creating Cloud Composer 3 environment: $ENV_NAME ==="
echo "Project: $PROJECT_ID"
echo "Region:  $REGION"
echo "Service account: $SA_EMAIL"
echo ""

# Enable required services
gcloud services enable composer.googleapis.com \
    cloudbuild.googleapis.com \
    container.googleapis.com

# Composer 3 requires an explicit service account and runs all Airflow
# tasks under it, so grant permissions before creating the environment.
echo "=== Granting required IAM permissions to $SA_EMAIL ==="
for ROLE in roles/documentai.apiUser roles/storage.admin roles/aiplatform.user roles/cloudsql.client roles/composer.worker; do
    echo "  Granting $ROLE ..."
    gcloud projects add-iam-policy-binding "$PROJECT_ID" \
        --member="serviceAccount:$SA_EMAIL" \
        --role="$ROLE" \
        --condition=None \
        --quiet > /dev/null
done
echo ""

# Create the environment (takes ~20-30 minutes).
# Worker memory is bumped above the "small" default (2GB) because
# process_file runs DocAI extraction + LangChain chunking, which OOMs
# small workers under concurrent task execution (mirrors the 512MB ->
# 1024MB bump needed for the equivalent Cloud Function).
gcloud composer environments create "$ENV_NAME" \
    --project="$PROJECT_ID" \
    --location="$REGION" \
    --environment-size=small \
    --image-version=composer-3-airflow-2.10.5 \
    --service-account="$SA_EMAIL" \
    --worker-memory=4GB \
    --worker-cpu=1 \
    --airflow-configs=core-default_task_retries=3

# Get the DAG bucket path
DAG_BUCKET=$(gcloud composer environments describe "$ENV_NAME" \
    --project="$PROJECT_ID" \
    --location="$REGION" \
    --format="value(config.dagGcsPrefix)")

echo ""
echo "=== DAG bucket: $DAG_BUCKET ==="

# Sync the DAG file
echo "=== Uploading DAG ==="
gsutil cp "$REPO_ROOT/dags/pipeline_dag.py" "$DAG_BUCKET/"

# Sync source code (the Composer workers need src.pipeline).
# NOTE: worker Celery processes cache Python imports for their pod
# lifetime, so re-running just this upload against an already-running
# environment (without a subsequent `environments update`, which forces
# a worker pod restart) will NOT pick up the new code — workers keep
# using whatever version of src.pipeline they first imported. This
# script's own PyPI-install step below forces that restart on a fresh
# deploy; if you're re-syncing source on a live environment, follow up
# with a trivial `gcloud composer environments update` to force it.
echo "=== Uploading source code ==="
COMPSRC="${DAG_BUCKET/dags/dags\/src\/pipeline}"
for f in "$REPO_ROOT"/src/pipeline/*.py; do
    gsutil cp "$f" "$COMPSRC/$(basename "$f")"
done

# Install the pipeline's runtime dependencies on the Composer workers.
# Composer only ships a base set of packages; process_file imports
# langchain, google-cloud-documentai/aiplatform, and pgvector/the Cloud
# SQL Python Connector, none of which are preinstalled.
echo ""
echo "=== Installing PyPI packages on Composer workers (takes a few minutes) ==="
gcloud composer environments update "$ENV_NAME" \
    --project="$PROJECT_ID" \
    --location="$REGION" \
    --update-pypi-packages-from-file="$REPO_ROOT/scripts/composer-requirements.txt"

# process_file calls PipelineConfig.from_env() directly (it does not read
# the PIPELINE_* Airflow Variables below), so every value PipelineConfig
# needs must exist as a real OS environment variable on the workers.
# DB_INSTANCE_CONNECTION_NAME routes VectorStore through the Cloud SQL
# Python Connector (IAM auth) instead of a direct TCP connection, since
# Composer workers have no stable IP to allowlist on the Cloud SQL
# instance and there's no proxy sidecar configured here.
echo ""
echo "=== Setting pipeline environment variables ==="
if [ -f "$REPO_ROOT/.env" ]; then
    # shellcheck disable=SC1090
    source "$REPO_ROOT/.env"
fi
# Note: GOOGLE_CLOUD_PROJECT is set automatically by Composer and cannot
# be overridden via --update-env-variables.
gcloud composer environments update "$ENV_NAME" \
    --project="$PROJECT_ID" \
    --location="$REGION" \
    --update-env-variables="DOCAI_LOCATION=${DOCAI_LOCATION:-us},DOCAI_PROCESSOR_ID=${DOCAI_PROCESSOR_ID:-},EMBEDDING_LOCATION=${EMBEDDING_LOCATION:-us-east1},EMBEDDING_MODEL=${EMBEDDING_MODEL:-text-embedding-005},EMBEDDING_DIMENSIONS=${EMBEDDING_DIMENSIONS:-768},INPUT_BUCKET=${INPUT_BUCKET:-corporate-raw-docs},OUTPUT_BUCKET=${OUTPUT_BUCKET:-corporate-processed-docs},DB_INSTANCE_CONNECTION_NAME=${DB_INSTANCE_CONNECTION_NAME:-},DB_NAME=${DB_NAME:-docpipeline},DB_USER=${DB_USER:-pipeline},DB_PASSWORD=${DB_PASSWORD:-},VECTOR_TABLE=${VECTOR_TABLE:-document_chunks}"

echo ""
echo "=== Setting Airflow Variables ==="
declare -A PIPELINE_VARS=(
    [PIPELINE_INPUT_BUCKET]="${INPUT_BUCKET:-corporate-raw-docs}"
    [PIPELINE_OUTPUT_BUCKET]="${OUTPUT_BUCKET:-corporate-processed-docs}"
    [PIPELINE_DEAD_LETTER_BUCKET]="corporate-dlq"
    [PIPELINE_MAX_FILES_PER_RUN]="50"
)
for VAR_NAME in "${!PIPELINE_VARS[@]}"; do
    VAR_VALUE="${PIPELINE_VARS[$VAR_NAME]}"
    echo "  $VAR_NAME = $VAR_VALUE"
    gcloud composer environments run "$ENV_NAME" \
        --project="$PROJECT_ID" \
        --location="$REGION" \
        variables set -- "$VAR_NAME" "$VAR_VALUE" > /dev/null
done
echo ""
echo "=== Done ==="
echo "Access the Airflow UI:"
BUCKET_PATH=${DAG_BUCKET%/dags}
FUNC_NAME="${ENV_NAME}"
echo "  gcloud composer environments describe $ENV_NAME \\"
echo "    --location=$REGION \\"
echo "    --format='value(config.airflowUri)'"
