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
    users = await conn.fetch("SELECT id, telegram_id, first_name, username, created_at FROM users ORDER BY created_at DESC")
    print(f"Found {len(users)} users in database.")
    
    if users:
        latest = users[0]
        # Delete user and all cascade data
        user_id = latest["id"]
        tg_id = latest["telegram_id"]
        await conn.execute(
            "UPDATE conversation_sessions SET active_order_id = NULL, active_payment_id = NULL WHERE user_id = $1",
            user_id,
        )
        await conn.execute(
            "DELETE FROM payment_review_messages WHERE payment_id IN (SELECT id FROM payments WHERE user_id = $1)",
            user_id,
        )
        await conn.execute(
            "DELETE FROM payment_proofs WHERE submitted_by_user_id = $1 OR payment_id IN (SELECT id FROM payments WHERE user_id = $1)",
            user_id,
        )
        await conn.execute(
            "DELETE FROM commissions WHERE order_id IN (SELECT id FROM orders WHERE user_id = $1) OR buyer_user_id = $1 OR referrer_user_id = $1",
            user_id,
        )
        await conn.execute(
            "DELETE FROM entitlements WHERE user_id = $1 OR granted_by_order_id IN (SELECT id FROM orders WHERE user_id = $1)",
            user_id,
        )
        await conn.execute("DELETE FROM payments WHERE user_id = $1", user_id)
        await conn.execute("DELETE FROM orders WHERE user_id = $1", user_id)
        await conn.execute("DELETE FROM referral_attributions WHERE referrer_user_id = $1", user_id)
        await conn.execute("DELETE FROM users WHERE id = $1", user_id)
        print(f"Successfully wiped latest user (Telegram ID: {tg_id})! You can now send /start from scratch.")
    else:
        print("No users in database.")

    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
