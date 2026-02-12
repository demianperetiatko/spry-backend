from __future__ import annotations

import mimetypes
import os
import uuid

import requests
from fastapi import UploadFile
from google.cloud import storage

from src.core.config import settings


class GCPBucket:
    @classmethod
    def get_client(cls) -> storage.Client | None:
        service_key_path = settings.GCP_SERVICE_KEY_PATH
        if not service_key_path or not os.path.exists(service_key_path):
            return None
        return storage.Client.from_service_account_json(service_key_path)

    @classmethod
    def upload_file(
        cls,
        file: UploadFile,
        prefix: str | None = None,
        filename: str | None = None,
    ) -> str | None:
        client = cls.get_client()
        if not client:
            return None

        if prefix is None:
            prefix = settings.GCP_DEFAULT_UPLOAD_PREFIX

        extension = os.path.splitext(file.filename or "")[1] if file.filename else ""
        if not extension:
            guessed_type, _ = mimetypes.guess_type(file.filename or "")
            extension = mimetypes.guess_extension(guessed_type or "") or ""

        if not filename:
            filename = str(uuid.uuid4())

        blob_name = f"{prefix}{filename}{extension}"
        bucket = client.bucket(settings.GCP_BUCKET_NAME)
        blob = bucket.blob(blob_name)
        blob.upload_from_file(file.file, content_type=file.content_type)

        return f"https://storage.googleapis.com/{settings.GCP_BUCKET_NAME}/{blob_name}"

    @classmethod
    def upload_file_from_url(
        cls,
        file_url: str,
        prefix: str | None = None,
        filename: str | None = None,
    ) -> str | None:
        client = cls.get_client()
        if not client:
            return None

        if prefix is None:
            prefix = settings.GCP_DEFAULT_UPLOAD_PREFIX

        response = requests.get(file_url, stream=True, timeout=30)
        response.raise_for_status()

        content_type = response.headers.get("Content-Type", "application/octet-stream")
        extension = mimetypes.guess_extension(content_type.split(";")[0]) or ""

        if not filename:
            filename = str(uuid.uuid4())

        blob_name = f"{prefix}{filename}{extension}"
        bucket = client.bucket(settings.GCP_BUCKET_NAME)
        blob = bucket.blob(blob_name)
        blob.upload_from_string(response.content, content_type=content_type)

        return f"https://storage.googleapis.com/{settings.GCP_BUCKET_NAME}/{blob_name}"


def get_gcp_bucket() -> type[GCPBucket]:
    return GCPBucket
