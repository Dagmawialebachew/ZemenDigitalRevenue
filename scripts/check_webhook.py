import asyncio
import sys
from pathlib import Path
import aiohttp

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.core.config import get_settings

async def main():
    token = get_settings().bot_token
    async with aiohttp.ClientSession() as session:
        async with session.get(f"https://api.telegram.org/bot{token}/getWebhookInfo") as r:
            data = await r.json()
            print("Webhook info:", data)
            if data.get("result", {}).get("url"):
                print("Old webhook detected! Deleting webhook so polling receives all updates...")
                async with session.get(f"https://api.telegram.org/bot{token}/deleteWebhook?drop_pending_updates=true") as dr:
                    print("Delete webhook result:", await dr.json())
            else:
                print("Webhook is empty (ready for direct polling).")

if __name__ == "__main__":
    asyncio.run(main())
