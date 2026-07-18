from xml.sax.saxutils import escape

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database import get_db
from db.product import Product
from utils.cache import cache_get, cache_set
from utils.limiter import limiter

router = APIRouter()

# Static, always-public customer pages — everything else (checkout/tracking/profile, admin,
# rider, auth) is either private (see the noindex meta tags on those pages, frontend/robots.txt)
# or has no useful indexable content of its own.
_STATIC_PAGES = ["customer/index.html", "customer/shop.html", "customer/about.html", "customer/contact.html"]


@router.get("/sitemap.xml")
@limiter.limit("30/minute")
async def sitemap(request: Request, db: AsyncSession = Depends(get_db)):
    """Generated on demand (cached 10 minutes — see utils/cache.py, same pattern as
    GET /products/categories) rather than a static file, since the product catalog changes
    independently of any frontend deploy and there's no build step in this vanilla-JS frontend
    to regenerate a static sitemap from."""
    cached = await cache_get("seo:sitemap")
    if cached is not None:
        return Response(content=cached, media_type="application/xml")

    base = settings.frontend_url.rstrip("/")
    urls = [f"{base}/{page}" for page in _STATIC_PAGES]

    result = await db.execute(select(Product.id, Product.updated_at).where(Product.is_active.is_(True)))
    for product_id, updated_at in result.all():
        urls.append(f"{base}/customer/product.html?id={product_id}")

    entries = "".join(f"<url><loc>{escape(url)}</loc></url>" for url in urls)
    xml = f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{entries}</urlset>'

    await cache_set("seo:sitemap", xml, ttl_seconds=600)
    return Response(content=xml, media_type="application/xml")
