import mimetypes
import os
import uuid

import requests
from fastapi import UploadFile
from google.cloud import storage

BUCKET_NAME = os.getenv("GCP_BUCKET_NAME")
DEFAULT_UPLOAD_PREFIX = "image/profile/"


def get_gcp_client() -> storage.Client | None:
    service_key_path = os.getenv("GCP_SERVICE_KEY_PATH")
    if not service_key_path or not os.path.exists(service_key_path):
        return None
    return storage.Client.from_service_account_json(service_key_path)


def upload_file(file: UploadFile, prefix: str = DEFAULT_UPLOAD_PREFIX, filename: str | None = None) -> str | None:
    client = get_gcp_client()
    if not client:
        return None

    bucket = client.bucket(BUCKET_NAME)

    extension = os.path.splitext(file.filename)[1] if file.filename else ""
    if not extension:
        guessed_type, _ = mimetypes.guess_type(file.filename or "")
        extension = mimetypes.guess_extension(guessed_type or "") or ""

    if not filename:
        filename = str(uuid.uuid4())

    blob_name = f"{prefix}{filename}{extension}"
    blob = bucket.blob(blob_name)
    blob.upload_from_file(file.file, content_type=file.content_type)

    return f"https://storage.googleapis.com/{BUCKET_NAME}/{blob_name}"


def upload_file_from_url(file_url: str, prefix: str = DEFAULT_UPLOAD_PREFIX, filename: str | None = None) -> str | None:
    client = get_gcp_client()
    if not client:
        return None

    response = requests.get(file_url, stream=True)
    response.raise_for_status()

    content_type = response.headers.get("Content-Type", "application/octet-stream")
    extension = mimetypes.guess_extension(content_type.split(";")[0]) or ""

    if not filename:
        filename = str(uuid.uuid4())

    blob_name = f"{prefix}{filename}{extension}"
    bucket = client.bucket(BUCKET_NAME)
    blob = bucket.blob(blob_name)
    blob.upload_from_string(response.content, content_type=content_type)

    return f"https://storage.googleapis.com/{BUCKET_NAME}/{blob_name}"


def delete_file(blob_name: str) -> None:
    client = get_gcp_client()
    if not client:
        return None

    bucket = client.bucket(BUCKET_NAME)
    blob = bucket.blob(blob_name)
    blob.delete()
