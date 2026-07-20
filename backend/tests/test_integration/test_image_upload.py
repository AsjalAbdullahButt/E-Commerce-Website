"""Tests for POST /admin/products/upload-image (routes/admin.py) and services/image_storage.py.
S3 is disabled by default (no credentials in the test environment) so every test here exercises
the local-disk storage path — the one actually usable without any third-party account.
"""
import asyncio
import io

import pytest
from PIL import Image

from config import settings
from services.admin_auth import AdminAuthService


def _admin_token(client, email="imageadmin@test.com", password="AdminPass123"):
    asyncio.run(AdminAuthService.create_admin_user(name="Admin", email=email, password=password, role="admin"))
    resp = client.post("/admin/auth/login", json={"email": email, "password": password})
    return resp.json()["data"]["access_token"]


def _register_customer(client, email="imagecustomer@test.com", password="Shopper123"):
    resp = client.post("/auth/register", json={
        "name": "Image Customer", "email": email, "password": password, "phone": "03001234567",
    })
    return resp.json()["access_token"]


def _fake_jpeg_bytes(size=(300, 300), color=(200, 30, 30)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="JPEG")
    return buf.getvalue()


def test_upload_valid_image_stores_locally_and_returns_urls(client):
    admin_token = _admin_token(client)
    resp = client.post(
        "/admin/products/upload-image",
        files={"file": ("product.jpg", _fake_jpeg_bytes(), "image/jpeg")},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["url"].startswith("http://testserver/uploads/products/")
    assert data["thumbnail_url"].startswith("http://testserver/uploads/products/thumbs/")
    assert data["url"] != data["thumbnail_url"]

    # The files actually landed on disk, not just a fabricated URL.
    from services.image_storage import UPLOADS_BASE
    uploaded_name = data["url"].rsplit("/", 1)[-1]
    thumb_name = data["thumbnail_url"].rsplit("/", 1)[-1]
    assert (UPLOADS_BASE / "products" / uploaded_name).exists()
    assert (UPLOADS_BASE / "products" / "thumbs" / thumb_name).exists()


def test_upload_rejects_non_image_file(client):
    admin_token = _admin_token(client, email="imageadmin2@test.com")
    resp = client.post(
        "/admin/products/upload-image",
        files={"file": ("not-an-image.txt", b"hello world", "text/plain")},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 400
    assert "Unsupported image type" in resp.json()["detail"]


def test_upload_rejects_file_with_image_extension_but_bad_content(client):
    """A .jpg extension with garbage bytes must still be rejected — the content-type header is
    client-supplied and can't be trusted; Pillow actually opens/verifies the bytes."""
    admin_token = _admin_token(client, email="imageadmin3@test.com")
    resp = client.post(
        "/admin/products/upload-image",
        files={"file": ("fake.jpg", b"not actually a jpeg", "image/jpeg")},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 400
    assert "not a valid image" in resp.json()["detail"]


def test_upload_rejects_oversized_file(client, monkeypatch):
    monkeypatch.setattr(settings, "max_image_upload_mb", 0)  # anything at all now exceeds the limit
    admin_token = _admin_token(client, email="imageadmin4@test.com")
    resp = client.post(
        "/admin/products/upload-image",
        files={"file": ("product.jpg", _fake_jpeg_bytes(), "image/jpeg")},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 400
    assert "exceeds" in resp.json()["detail"]


def test_streaming_read_enforces_limit_independent_of_content_length(monkeypatch):
    """Content-Length is a client-supplied hint (services/image_storage.py checks it as a fast
    fail) -- the byte-counted streaming read is what actually enforces max_image_upload_mb, so
    it must reject an oversized body even when no Content-Length is available at all (e.g.
    chunked transfer encoding), not just when the header happens to be present and honest."""
    monkeypatch.setattr(settings, "max_image_upload_mb", 0)
    from services.image_storage import ImageStorageService

    class _ChunkedFakeUploadFile:
        """Stands in for an UploadFile with no known Content-Length up front."""
        def __init__(self, data: bytes):
            self._buf = io.BytesIO(data)

        async def read(self, n=-1):
            return self._buf.read(n)

    fake_file = _ChunkedFakeUploadFile(_fake_jpeg_bytes())

    async def _run():
        with pytest.raises(Exception) as exc_info:
            await ImageStorageService._read_with_limit(fake_file, max_bytes=0)
        return exc_info.value

    error = asyncio.run(_run())
    assert getattr(error, "status_code", None) == 400
    assert "exceeds" in error.detail


def test_upload_rejects_decompression_bomb(client, monkeypatch):
    """A small-on-disk image that decodes to a huge pixel grid must be rejected cleanly (400),
    not crash the request -- Image.MAX_IMAGE_PIXELS is set in services/image_storage.py, and
    Image.DecompressionBombError is not an OSError subclass, so it needs its own except branch."""
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 1000)  # anything at all now counts as a bomb
    admin_token = _admin_token(client, email="imageadmin7@test.com")

    resp = client.post(
        "/admin/products/upload-image",
        files={"file": ("product.jpg", _fake_jpeg_bytes(size=(300, 300)), "image/jpeg")},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 400
    assert "too large" in resp.json()["detail"]


def test_upload_requires_admin_permission(client):
    customer_token = _register_customer(client)
    resp = client.post(
        "/admin/products/upload-image",
        files={"file": ("product.jpg", _fake_jpeg_bytes(), "image/jpeg")},
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert resp.status_code in (401, 403)


def test_uploaded_image_is_servable_via_static_route(client):
    admin_token = _admin_token(client, email="imageadmin5@test.com")
    upload_resp = client.post(
        "/admin/products/upload-image",
        files={"file": ("product.jpg", _fake_jpeg_bytes(), "image/jpeg")},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    url = upload_resp.json()["data"]["url"]
    path = "/" + url.split("/", 3)[-1]  # strip the http://testserver prefix, keep /uploads/...

    fetch_resp = client.get(path)
    assert fetch_resp.status_code == 200
    assert fetch_resp.headers["content-type"].startswith("image/")


def test_uploaded_image_url_can_be_attached_to_a_product(client):
    """The upload endpoint only returns a URL — attaching it to a product still goes through the
    existing POST /admin/products, which already accepts a plain list of image URL strings."""
    admin_token = _admin_token(client, email="imageadmin6@test.com")
    upload_resp = client.post(
        "/admin/products/upload-image",
        files={"file": ("product.jpg", _fake_jpeg_bytes(), "image/jpeg")},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    uploaded_url = upload_resp.json()["data"]["url"]

    create_resp = client.post(
        "/admin/products",
        json={
            "name": "Uploaded Image Product", "description": "test", "category": "accessories",
            "price": 750, "discount_percentage": 0, "tags": [], "images": [uploaded_url],
            "variants": [{"size": "One Size", "color": "Black", "sku": "uploaded-image-item", "stock": 5}],
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert create_resp.status_code == 200, create_resp.text
    product_id = create_resp.json()["data"]["product_id"]

    product_resp = client.get(f"/products/{product_id}")
    assert product_resp.json()["images"] == [uploaded_url]
