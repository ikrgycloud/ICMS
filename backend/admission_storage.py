"""Private storage for applicant documents.

S3 is used when S3_BUCKET is configured. The local fallback keeps development
usable without cloud credentials and must not be used for production uploads.
"""
import os
from pathlib import Path
from urllib.parse import urlparse

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError


class AdmissionDocumentStorage:
    def __init__(self):
        self.bucket = os.getenv("S3_BUCKET", "").strip()
        self.region = os.getenv("S3_REGION", "").strip() or None
        self.endpoint_url = os.getenv("S3_ENDPOINT_URL", "").strip() or None
        self.local_root = Path(__file__).resolve().parent / "uploads" / "admissions"
        self._client = None

    @property
    def uses_s3(self):
        return bool(self.bucket)

    def _s3(self):
        if not self._client:
            self._client = boto3.client(
                "s3",
                region_name=self.region,
                endpoint_url=self.endpoint_url,
                config=Config(s3={"addressing_style": "path"}),
            )
        return self._client

    def put(self, application_id, filename, content, mime_type, object_id):
        suffix = Path(filename).suffix[:12]
        object_key = f"admissions/{application_id}/{object_id}{suffix}"
        if self.uses_s3:
            try:
                self._s3().put_object(
                    Bucket=self.bucket,
                    Key=object_key,
                    Body=content,
                    ContentType=mime_type or "application/octet-stream",
                    ServerSideEncryption="AES256",
                )
            except (BotoCoreError, ClientError) as exc:
                raise RuntimeError("Could not store the document in S3") from exc
            return f"s3://{self.bucket}/{object_key}"

        directory = self.local_root / application_id
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / f"{object_id}{suffix}"
        target.write_bytes(content)
        return str(target.relative_to(Path(__file__).resolve().parent))

    def read(self, storage_key):
        if storage_key.startswith("s3://"):
            parsed = urlparse(storage_key)
            if not parsed.netloc or not parsed.path.lstrip("/"):
                raise FileNotFoundError("Invalid S3 document key")
            try:
                response = self._s3().get_object(Bucket=parsed.netloc, Key=parsed.path.lstrip("/"))
                return response["Body"].read(), response.get("ContentType")
            except (BotoCoreError, ClientError) as exc:
                raise FileNotFoundError("Document is unavailable") from exc

        root = Path(__file__).resolve().parent
        target = (root / storage_key).resolve()
        if root not in target.parents or not target.is_file():
            raise FileNotFoundError("Document is unavailable")
        return target.read_bytes(), None


document_storage = AdmissionDocumentStorage()
