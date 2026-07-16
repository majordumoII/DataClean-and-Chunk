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

# Sync source code (the Composer workers need src.pipeline)
echo "=== Uploading source code ==="
COMPSRC="${DAG_BUCKET/dags/dags\/src\/pipeline}"
gsutil cp -r "$REPO_ROOT"/src/pipeline/*.py "$COMPSRC/"

# Install the pipeline's runtime dependencies on the Composer workers.
# Composer only ships a base set of packages; process_file imports
# langchain, google-cloud-documentai/aiplatform, and psycopg2/pgvector,
# none of which are preinstalled.
echo ""
echo "=== Installing PyPI packages on Composer workers (takes a few minutes) ==="
gcloud composer environments update "$ENV_NAME" \
    --project="$PROJECT_ID" \
    --location="$REGION" \
    --update-pypi-packages-from-file="$REPO_ROOT/scripts/composer-requirements.txt"

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
