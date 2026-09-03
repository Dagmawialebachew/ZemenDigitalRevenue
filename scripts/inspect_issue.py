import asyncio
import asyncpg
from backend.core.config import get_settings

async def main():
    conn = await asyncpg.connect(get_settings().database_url)
    orders = await conn.fetch("SELECT id, public_id, user_id, total_due_br, pricing_type, customer_offer_id, created_at FROM orders ORDER BY created_at DESC LIMIT 5")
    print("=== RECENT ORDERS ===")
    for o in orders:
        print(dict(o))
    
    rules = await conn.fetch("SELECT * FROM discount_rules")
    print("\n=== DISCOUNT RULES ===")
    for r in rules:
        print(dict(r))

    offers = await conn.fetch("SELECT * FROM customer_offers")
    print("\n=== CUSTOMER OFFERS ===")
    for f in offers:
        print(dict(f))

    products = await conn.fetch("SELECT id, slug, regular_price_br, discounts_enabled FROM products")
    print("\n=== PRODUCTS ===")
    for p in products:
        print(dict(p))

    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
