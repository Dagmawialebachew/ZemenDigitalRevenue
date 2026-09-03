import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import asyncpg
from backend.core.config import get_settings

async def main():
    settings = get_settings()
    conn = await asyncpg.connect(settings.database_url)
    products = await conn.fetch("SELECT id, slug, status, regular_price_br FROM products")
    print(f"Found {len(products)} products:")
    for p in products:
        print(f" - {p['slug']} ({p['status']}): {p['regular_price_br']} Br (ID: {p['id']})")
    
    if not products:
        print("No products found. Creating default 'ai-kezero' product...")
        product_id = await conn.fetchval(
            """
            INSERT INTO products (
                slug, status, product_type, category, default_language,
                regular_price_br, recovery_price_br, discounts_enabled,
                referral_enabled, referral_commission_percent, commission_only_full_price,
                featured, sort_order
            ) VALUES (
                'ai-kezero', 'active', 'digital_file', 'AI / Practical Guide', 'am',
                549.00, 299.00, TRUE,
                TRUE, 10.00, TRUE,
                TRUE, 1
            ) RETURNING id
            """
        )
        await conn.execute(
            """
            INSERT INTO product_translations (product_id, language, title, subtitle, short_description, description, benefits)
            VALUES (
                $1, 'am',
                '«AI ከዜሮ» (AI From Zero)',
                'የዕለት ተዕለት ስራዎንና ቢዝነስዎን በAI የሚያቀላጥፉበት ተግባራዊ መመሪያ',
                'ባለ 131 ገጽ ተግባራዊ የአማርኛ መመሪያ + 27+ ዝግጁ Prompts ለቢሮ፣ ለስራ እና ለቢዝነስ አውቶሜሽን።',
                'ይህ መጽሐፍ ChatGPT እና AIን ከዜሮ ጀምረው በስራዎ ላይ ውጤት እንድታመጡበት በግልጽ አማርኛ የተዘጋጀ ነው።',
                ARRAY['ባለ 131 ገጽ ተግባራዊ መመሪያ', '27+ ዝግጁ Copy-Paste Prompts', 'የስራና የቢዝነስ አውቶሜሽን ምሳሌዎች', 'ምንም የቴክኖሎጂ እውቀት አይጠይቅም']
            )
            """,
            product_id,
        )
        await conn.execute(
            """
            INSERT INTO product_translations (product_id, language, title, subtitle, short_description, description, benefits)
            VALUES (
                $1, 'en',
                'AI From Zero',
                'Complete practical Amharic guide to automate your career and business with AI',
                'Complete 131-page practical guide + 27+ copy-paste prompts for career, business and office automation.',
                'Master practical AI tools with step-by-step guidance tailored for real-world execution.',
                ARRAY['131-page comprehensive guide', '27+ ready prompts', 'Office & career workflows']
            )
            """,
            product_id,
        )
        print(f"Created active product 'ai-kezero' with ID: {product_id}")

    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
