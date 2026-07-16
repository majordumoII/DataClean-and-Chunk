#!/usr/bin/env bash
set -euo pipefail

# Creates a Cloud Composer 3 environment and syncs the DAG.
# Usage: ./scripts/setup-composer.sh [environment-name] [region]

ENV_NAME="${1:-docpipeline-composer}"
REGION="${2:-us-central1}"
PROJECT_ID=$(gcloud config get project)

echo "=== Creating Cloud Composer 3 environment: $ENV_NAME ==="
echo "Project: $PROJECT_ID"
echo "Region:  $REGION"
echo ""

# Enable required services
gcloud services enable composer.googleapis.com \
    cloudbuild.googleapis.com \
    container.googleapis.com

# Create the environment (takes ~20-30 minutes)
gcloud composer environments create "$ENV_NAME" \
    --project="$PROJECT_ID" \
    --location="$REGION" \
    --environment-size=small \
    --python-version=3 \
    --image-version=composer-3-airflow-2.10.3 \
    --airflow-configs=core-default_task_retries=3 \
    --node-count=3

# Get the DAG bucket path
DAG_BUCKET=$(gcloud composer environments describe "$ENV_NAME" \
    --project="$PROJECT_ID" \
    --location="$REGION" \
    --format="value(config.dagGcsPrefix)")

echo ""
echo "=== DAG bucket: $DAG_BUCKET ==="

# Sync the DAG file
echo "=== Uploading DAG ==="
gsutil cp ../dags/pipeline_dag.py "$DAG_BUCKET/"

# Sync source code (the Composer workers need src.pipeline)
echo "=== Uploading source code ==="
COMPSRC="${DAG_BUCKET/dags/dags\/src\/pipeline}"
gsutil cp -r ../src/pipeline/*.py "$COMPSRC/"

echo ""
echo "=== Airflow Variable config ==="
echo "Set these in the Airflow UI (Admin → Variables) or via gcloud:"
echo ""
echo "  PIPELINE_INPUT_BUCKET       = corporate-raw-docs"
echo "  PIPELINE_OUTPUT_BUCKET      = corporate-processed-docs"
echo "  PIPELINE_DEAD_LETTER_BUCKET = corporate-dlq"
echo "  PIPELINE_MAX_FILES_PER_RUN  = 50"
echo ""
echo "Or set via gcloud:"
echo "  gcloud composer environments run $ENV_NAME \\"
echo "    --location=$REGION \\"
echo "    variables set -- PIPELINE_DEAD_LETTER_BUCKET corporate-dlq"
echo ""
echo "=== Required IAM permissions ==="
echo "The Composer service account needs:"
echo "  - Document AI User"
echo "  - Storage Admin"
echo "  - Cloud SQL Client"
echo "  - Vertex AI User"
echo "  - Cloud Run Invoker (if using Cloud Function)"
echo ""
echo "Grant via:"
echo "  SA=\$(gcloud composer environments describe $ENV_NAME \\"
echo "    --location=$REGION \\"
echo "    --format='value(config.workloadsConfig.scheduler.serviceAccount'))"
echo "  gcloud projects add-iam-policy-binding $PROJECT_ID \\"
echo "    --member=\"serviceAccount:\$SA\" \\"
echo "    --role=roles/documentai.user"
echo "  gcloud projects add-iam-policy-binding $PROJECT_ID \\"
echo "    --member=\"serviceAccount:\$SA\" \\"
echo "    --role=roles/storage.admin"
echo "  gcloud projects add-iam-policy-binding $PROJECT_ID \\"
echo "    --member=\"serviceAccount:\$SA\" \\"
echo "    --role=roles/aiplatform.user"
echo "  gcloud projects add-iam-policy-binding $PROJECT_ID \\"
echo "    --member=\"serviceAccount:\$SA\" \\"
echo "    --role=roles/cloudsql.client"
echo ""
echo "=== Done ==="
echo "Access the Airflow UI:"
BUCKET_PATH=${DAG_BUCKET%/dags}
FUNC_NAME="${ENV_NAME}"
echo "  gcloud composer environments describe $ENV_NAME \\"
echo "    --location=$REGION \\"
echo "    --format='value(config.airflowUri)'"
