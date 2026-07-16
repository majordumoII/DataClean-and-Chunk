"""Tests for the Cloud Function event handler (with mocked PipelineRunner)."""

import base64
import json
from unittest.mock import MagicMock, patch

import pytest

from src.pipeline.event_handler import handle_gcs_event


def _gcs_object_resource(bucket="corporate-raw-docs", name="doc.pdf"):
    """The GCS object resource JSON GCS puts in the Pub/Sub message body.

    Note: this body has no "eventType" field — GCS puts eventType,
    bucketId, and objectId in the Pub/Sub message *attributes* instead.
    """
    return {
        "kind": "storage#object",
        "name": name,
        "bucket": bucket,
        "contentType": "application/pdf",
    }


def _encode(obj: dict) -> str:
    return base64.b64encode(json.dumps(obj).encode("utf-8")).decode("utf-8")


class TestHandleGcsEvent:
    @patch("src.pipeline.event_handler.PipelineRunner")
    @patch("src.pipeline.event_handler.PipelineConfig")
    def test_gen1_background_event_processes_pdf(self, mock_config_cls, mock_runner_cls, config):
        mock_config_cls.from_env.return_value = config
        mock_runner = MagicMock()
        mock_runner_cls.return_value = mock_runner

        data = {
            "data": _encode(_gcs_object_resource(name="doc.pdf")),
            "attributes": {
                "bucketId": "corporate-raw-docs",
                "objectId": "doc.pdf",
                "eventType": "OBJECT_FINALIZE",
            },
        }
        context = MagicMock(event_id="123")

        handle_gcs_event(data, context)

        mock_runner.process_file_and_upload.assert_called_once_with(
            "gs://corporate-raw-docs/doc.pdf"
        )

    @patch("src.pipeline.event_handler.PipelineRunner")
    @patch("src.pipeline.event_handler.PipelineConfig")
    def test_skips_non_finalize_event_type(self, mock_config_cls, mock_runner_cls, config):
        mock_runner = MagicMock()
        mock_runner_cls.return_value = mock_runner

        data = {
            "data": _encode(_gcs_object_resource(name="doc.pdf")),
            "attributes": {
                "bucketId": "corporate-raw-docs",
                "objectId": "doc.pdf",
                "eventType": "OBJECT_DELETE",
            },
        }
        context = MagicMock(event_id="123")

        handle_gcs_event(data, context)

        mock_runner.process_file_and_upload.assert_not_called()

    @patch("src.pipeline.event_handler.PipelineRunner")
    @patch("src.pipeline.event_handler.PipelineConfig")
    def test_skips_non_pdf(self, mock_config_cls, mock_runner_cls, config):
        mock_runner = MagicMock()
        mock_runner_cls.return_value = mock_runner

        data = {
            "data": _encode(_gcs_object_resource(name="doc.txt")),
            "attributes": {
                "bucketId": "corporate-raw-docs",
                "objectId": "doc.txt",
                "eventType": "OBJECT_FINALIZE",
            },
        }
        context = MagicMock(event_id="123")

        handle_gcs_event(data, context)

        mock_runner.process_file_and_upload.assert_not_called()

    @patch("src.pipeline.event_handler.PipelineRunner")
    @patch("src.pipeline.event_handler.PipelineConfig")
    def test_falls_back_to_body_when_attributes_missing(
        self, mock_config_cls, mock_runner_cls, config
    ):
        """Some callers may not include Pub/Sub attributes; the decoded
        GCS object body still carries bucket/name (but never eventType)."""
        mock_config_cls.from_env.return_value = config
        mock_runner = MagicMock()
        mock_runner_cls.return_value = mock_runner

        data = {"data": _encode(_gcs_object_resource(name="doc.pdf"))}
        context = MagicMock(event_id="123")

        handle_gcs_event(data, context)

        # No attributes means no eventType, so it must NOT process.
        mock_runner.process_file_and_upload.assert_not_called()

    @patch("src.pipeline.event_handler.PipelineRunner")
    @patch("src.pipeline.event_handler.PipelineConfig")
    def test_gen2_cloudevent_wrapped_message(self, mock_config_cls, mock_runner_cls, config):
        mock_config_cls.from_env.return_value = config
        mock_runner = MagicMock()
        mock_runner_cls.return_value = mock_runner

        cloud_event = MagicMock()
        cloud_event.get.return_value = "event-id"
        cloud_event.data = {
            "message": {
                "data": _encode(_gcs_object_resource(name="doc.pdf")),
                "attributes": {
                    "bucketId": "corporate-raw-docs",
                    "objectId": "doc.pdf",
                    "eventType": "OBJECT_FINALIZE",
                },
            }
        }

        handle_gcs_event(cloud_event)

        mock_runner.process_file_and_upload.assert_called_once_with(
            "gs://corporate-raw-docs/doc.pdf"
        )

    def test_no_args_returns_without_raising(self):
        handle_gcs_event()
