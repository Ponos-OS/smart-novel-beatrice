"""
Stand-in for a client's `genUploadUrl` endpoint, backed by a real S3-compatible store.

Beatrice's worker POSTs here expecting `{"url": "<presigned-url>"}`
(see `src/modules/audio/worker.py::_fetch_presigned_upload_url`), then PUTs the
generated audio to that URL. Every call mints a fresh presigned PUT URL for a
new object key, matching how a real client would.
"""

import os
import uuid
from datetime import timedelta

import boto3
from botocore.config import Config
from fastapi import FastAPI


S3_ENDPOINT = os.environ["S3_ENDPOINT"]
S3_ACCESS_KEY = os.environ["S3_ACCESS_KEY"]
S3_SECRET_KEY = os.environ["S3_SECRET_KEY"]
S3_BUCKET = os.environ["S3_BUCKET"]

app = FastAPI()
client = boto3.client(
    "s3",
    endpoint_url=f"http://{S3_ENDPOINT}",
    aws_access_key_id=S3_ACCESS_KEY,
    aws_secret_access_key=S3_SECRET_KEY,
    region_name="us-east-1",
    config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
)


@app.get("/health")
def health() -> dict[str, bool]:
    return {"ok": True}


@app.post("/presign")
def presign() -> dict[str, str]:
    object_name = f"{uuid.uuid4()}.mp3"
    url = client.generate_presigned_url(
        "put_object",
        Params={"Bucket": S3_BUCKET, "Key": object_name},
        ExpiresIn=int(timedelta(minutes=10).total_seconds()),
    )
    return {"url": url}
