#!/usr/bin/env bash
set -euo pipefail

# Run the Cloud SQL Auth Proxy to connect locally to a Cloud SQL instance.
# You'll need the Cloud SQL Auth Proxy binary:
#   https://cloud.google.com/sql/docs/postgres/connect-auth-proxy

PROJECT="${1:?"Usage: $0 <project-id> <instance-name> [port]"}
INSTANCE="${2:?"Usage: $0 <project-id> <instance-name> [port]"}"
PORT="${3:-5432}"

echo "Starting Cloud SQL Auth Proxy for $PROJECT:$INSTANCE on port $PORT ..."
exec cloud-sql-proxy "$PROJECT:$INSTANCE" --port "$PORT"
