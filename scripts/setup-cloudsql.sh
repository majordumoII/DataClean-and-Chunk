#!/usr/bin/env bash
set -euo pipefail

# Creates a Cloud SQL for PostgreSQL instance + database for pgvector.
# Requires: gcloud, a GCP project set in .env

PROJECT_ID="${1:?"Usage: $0 <project-id> [instance-name] [db-name]"}"
INSTANCE="${2:-docpipeline-db}"
DB="${3:-docpipeline}"
PASSWORD="${PGPASSWORD:-changeme}"

echo "=== Creating Cloud SQL PostgreSQL instance: $INSTANCE ==="
gcloud sql instances create "$INSTANCE" \
    --project="$PROJECT_ID" \
    --database-version=POSTGRES_17 \
    --tier=db-custom-1-3840 \
    --region=us-central1 \
    --root-password="$PASSWORD"

echo "=== Creating database: $DB ==="
gcloud sql databases create "$DB" \
    --project="$PROJECT_ID" \
    --instance="$INSTANCE"

echo "=== Creating user: pipeline ==="
gcloud sql users create pipeline \
    --project="$PROJECT_ID" \
    --instance="$INSTANCE" \
    --password="$PASSWORD"

PUBLIC_IP=$(gcloud sql instances describe "$INSTANCE" \
    --project="$PROJECT_ID" \
    --format="value(ipAddresses[0].ipAddress)")

echo ""
echo "=== Connection info ==="
echo "  Public IP:  $PUBLIC_IP"
echo "  Connection string:"
echo "    postgresql://pipeline:$PASSWORD@$PUBLIC_IP:5432/$DB"
echo ""
echo "To access via Cloud SQL Auth Proxy (recommended):"
echo "  ./scripts/start-cloudsql-proxy.sh $PROJECT_ID $INSTANCE"
echo "Then use:"
echo "    postgresql://pipeline:$PASSWORD@localhost:5432/$DB"
