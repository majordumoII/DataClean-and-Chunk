"""Cloud Function entry point — triggered by GCS events via Pub/Sub.

Deploy this function so that new PDF uploads to corporate-raw-docs
are automatically processed by the pipeline.

To deploy:
    gcloud functions deploy docai-pipeline \
        --runtime python313 \
        --trigger-topic corporate-raw-docs-notify \
        --source . \
        --entry-point handle_gcs_event \
        --env-vars-file .env.yaml \
        --memory 512MB \
        --timeout 300s
"""

import base64
import json
import logging
import os

from dotenv import load_dotenv

load_dotenv()

from src.pipeline.config import PipelineConfig
from src.pipeline.runner import PipelineRunner

logger = logging.getLogger(__name__)


def handle_gcs_event(cloud_event):
    """Cloud Function entry point. Called via Eventarc / CloudEvents.

    Expects a CloudEvent wrapping a Pub/Sub message with GCS notification
    payload (as sent by GCS notification config).
    """
    logger.info("Received event: %s", cloud_event["id"])

    # Decode the Pub/Sub message data
    data = cloud_event.data
    if isinstance(data, dict) and "message" in data:
        message = data["message"]
    elif isinstance(data, dict):
        message = data
    else:
        logger.error("Unexpected event format")
        return

    encoded_data = message.get("data", "")
    if not encoded_data:
        logger.warning("No data in message")
        return

    try:
        decoded = base64.b64decode(encoded_data).decode("utf-8")
        notification = json.loads(decoded)
    except Exception as e:
        logger.error("Failed to decode message: %s", e)
        return

    # Extract bucket and object name from GCS notification
    bucket = notification.get("bucket")
    name = notification.get("name")
    event_type = notification.get("eventType", "")

    if not bucket or not name:
        logger.warning("Notification missing bucket or name: %s", notification)
        return

    # Only process OBJECT_FINALIZE events (new object creation)
    if event_type != "OBJECT_FINALIZE":
        logger.debug("Skipping event type: %s", event_type)
        return

    # Only process PDFs
    if not name.lower().endswith(".pdf"):
        logger.debug("Skipping non-PDF: %s", name)
        return

    gcs_uri = f"gs://{bucket}/{name}"
    logger.info("Processing new PDF: %s", gcs_uri)

    config = PipelineConfig.from_env()
    runner = PipelineRunner(config)

    try:
        output = runner.process_file_and_upload(gcs_uri)
        logger.info("Success: %s", output)
    except Exception as e:
        logger.error("Failed to process %s: %s", gcs_uri, e)
        raise
