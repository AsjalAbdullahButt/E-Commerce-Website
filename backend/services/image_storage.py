import io
import uuid
from pathlib import Path
from typing import Tuple

from fastapi import HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError
from starlette.concurrency import run_in_threadpool

from config import settings

ALLOWED_CONTENT_TYPES = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
THUMBNAIL_SIZE = (400, 400)

UPLOADS_BASE = Path(__file__).resolve().parent.parent / "uploads"


class ImageStorageService:
    """Generic image upload — validates the file, generates a thumbnail, and stores both to
    local disk (default, fully functional with zero credentials) or S3 (once s3_enabled is set).
    See config/settings.py for the S3_* flags. `category` picks the storage subfolder/S3 prefix
    ("products" for the admin catalog, "delivery-proof" for rider proof-of-delivery photos, etc.)
    so unrelated upload types don't collide or share one unbounded directory."""

    @staticmethod
    def _validate(file_bytes: bytes, content_type: str) -> Image.Image:
        if content_type not in ALLOWED_CONTENT_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported image type: {content_type}. Allowed: JPEG, PNG, WEBP",
            )
        max_bytes = settings.max_image_upload_mb * 1024 * 1024
        if len(file_bytes) > max_bytes:
            raise HTTPException(status_code=400, detail=f"Image exceeds the {settings.max_image_upload_mb}MB limit")

        try:
            probe = Image.open(io.BytesIO(file_bytes))
            probe.verify()  # raises if the bytes aren't actually a valid image, whatever the extension/header claims
            img = Image.open(io.BytesIO(file_bytes))  # verify() consumes the file handle — reopen to actually use it
            img.load()
        except (UnidentifiedImageError, OSError):
            raise HTTPException(status_code=400, detail="File is not a valid image")
        return img

    @staticmethod
    def _make_thumbnail(img: Image.Image) -> bytes:
        thumb = img.convert("RGB").copy()
        thumb.thumbnail(THUMBNAIL_SIZE)
        buf = io.BytesIO()
        thumb.save(buf, format="JPEG", quality=85)
        return buf.getvalue()

    @staticmethod
    async def upload(file: UploadFile, base_url: str, category: str = "products") -> Tuple[str, str]:
        """Returns (url, thumbnail_url)."""
        file_bytes = await file.read()
        img = ImageStorageService._validate(file_bytes, file.content_type)
        ext = ALLOWED_CONTENT_TYPES[file.content_type]
        key = f"{uuid.uuid4().hex}.{ext}"
        thumb_bytes = await run_in_threadpool(ImageStorageService._make_thumbnail, img)

        if settings.s3_enabled:
            return await ImageStorageService._upload_to_s3(key, file_bytes, thumb_bytes, file.content_type, category)
        return ImageStorageService._upload_to_disk(key, file_bytes, thumb_bytes, base_url, category)

    @staticmethod
    def _upload_to_disk(key: str, file_bytes: bytes, thumb_bytes: bytes, base_url: str, category: str) -> Tuple[str, str]:
        upload_root = UPLOADS_BASE / category
        thumb_root = upload_root / "thumbs"
        upload_root.mkdir(parents=True, exist_ok=True)
        thumb_root.mkdir(parents=True, exist_ok=True)

        thumb_key = f"{Path(key).stem}_thumb.jpg"
        (upload_root / key).write_bytes(file_bytes)
        (thumb_root / thumb_key).write_bytes(thumb_bytes)

        base = base_url.rstrip("/")
        return f"{base}/uploads/{category}/{key}", f"{base}/uploads/{category}/thumbs/{thumb_key}"

    @staticmethod
    async def _upload_to_s3(key: str, file_bytes: bytes, thumb_bytes: bytes, content_type: str, category: str) -> Tuple[str, str]:
        def _put_objects() -> None:
            import boto3
            client = boto3.client(
                "s3",
                region_name=settings.s3_region,
                aws_access_key_id=settings.s3_access_key,
                aws_secret_access_key=settings.s3_secret_key,
                endpoint_url=settings.s3_endpoint_url or None,
            )
            client.put_object(Bucket=settings.s3_bucket, Key=full_key, Body=file_bytes, ContentType=content_type, ACL="public-read")
            client.put_object(Bucket=settings.s3_bucket, Key=thumb_key, Body=thumb_bytes, ContentType="image/jpeg", ACL="public-read")

        full_key = f"{category}/{key}"
        thumb_key = f"{category}/thumbs/{Path(key).stem}_thumb.jpg"
        # boto3 is a blocking/synchronous client — run it off the event loop rather than stalling
        # every other in-flight request for the duration of the network round trip.
        await run_in_threadpool(_put_objects)

        base = settings.s3_public_url_base.rstrip("/")
        return f"{base}/{full_key}", f"{base}/{thumb_key}"
