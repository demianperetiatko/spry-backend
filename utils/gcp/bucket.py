import os
import uuid
import requests
import mimetypes
from google.cloud import storage
from fastapi import UploadFile

BUCKET_NAME = os.getenv("GCP_BUCKET_NAME")
DEFAULT_UPLOAD_PREFIX = "image/profile/"


def get_gcp_client() -> storage.Client:
    return storage.Client.from_service_account_json(
        os.getenv("GCP_SERVICE_KEY_PATH")
    )


def upload_file(file: UploadFile, prefix: str = DEFAULT_UPLOAD_PREFIX, filename: str | None = None) -> str:
    client = get_gcp_client()
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


def upload_file_from_url(file_url: str, prefix: str = DEFAULT_UPLOAD_PREFIX, filename: str | None = None) -> str:
    response = requests.get(file_url, stream=True)
    response.raise_for_status()

    content_type = response.headers.get("Content-Type", "application/octet-stream")
    extension = mimetypes.guess_extension(content_type.split(";")[0]) or ""

    if not filename:
        filename = str(uuid.uuid4())

    blob_name = f"{prefix}{filename}{extension}"

    client = get_gcp_client()
    bucket = client.bucket(BUCKET_NAME)
    blob = bucket.blob(blob_name)

    blob.upload_from_string(response.content, content_type=content_type)

    return f"https://storage.googleapis.com/{BUCKET_NAME}/{blob_name}"


def delete_file(blob_name: str) -> None:
    client = get_gcp_client()
    bucket = client.bucket(BUCKET_NAME)
    blob = bucket.blob(blob_name)
    blob.delete()
