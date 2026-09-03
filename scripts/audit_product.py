import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import asyncpg
from backend.core.config import get_settings

async def main():
    conn = await asyncpg.connect(get_settings().database_url)
    product = await conn.fetchrow("SELECT id, slug, regular_price_br FROM products WHERE slug='ai-kezero'")
    if not product:
        print("Product 'ai-kezero' not found!")
        await conn.close()
        return

    pid = product["id"]
    print(f"Product: {product['slug']} ({product['regular_price_br']} Br)")
    
    media = await conn.fetch("SELECT id, media_type, storage_type, value, caption FROM product_media WHERE product_id=$1", pid)
    print(f"Media items ({len(media)}):")
    for m in media:
        print(f" - {m['media_type']} ({m['storage_type']}): {m['value'][:40]}... (caption: {m['caption']})")
    
    files = await conn.fetch("SELECT id, filename, version, is_active, storage_type FROM product_files WHERE product_id=$1", pid)
    print(f"Delivery files ({len(files)}):")
    for f in files:
        print(f" - {f['filename']} v{f['version']} (active: {f['is_active']}, storage: {f['storage_type']})")

    tracking_links = await conn.fetch("SELECT id, token, source, campaign, creative FROM tracking_links")
    print(f"Tracking links ({len(tracking_links)}):")
    for tl in tracking_links:
        print(f" - Token: {tl['token']} | Source: {tl['source']} | Campaign: {tl['campaign']}")

    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
