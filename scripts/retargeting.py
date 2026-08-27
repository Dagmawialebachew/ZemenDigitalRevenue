"""
Text-only high-intent retargeting launcher.

Usage:
    python scripts/retargeting.py
    python scripts/retargeting.py --dry-run

The launcher previews the message and audience before creating anything. It
uses the existing PostgreSQL-backed broadcast engine and never sends directly
from this process.
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, datetime
from pathlib import Path
import sys
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.core.config import get_settings
from backend.db.pool import Database
from backend.domain.marketing import normalize_audience
from backend.services.marketing import MarketingService

PRODUCT_SLUG = "ai-kezero"
CAMPAIGN_NAME = "High-Intent Retargeting · AI ከዜሮ"


# Keep the action copy at the end of the message so the value proposition is
# read before the buyer sees the choices.
def retargeting_copy() -> tuple[str, str]:
    amharic = """<b>🚨 ሌሎች ስራቸውን በAI በደቂቃዎች ውስጥ ሲያጠናቅቁ፣ እርስዎ አሁንም በድካም ጊዜዎን እያባከኑ ነው?</b>

ችግሩ <i>AI አለመቻልዎ</i> አይደለም፤ ትክክለኛውን ጥያቄና አጠቃቀም በተደራጀ መንገድ አለማወቅዎ ነው።

📘 <b>“AI ከዜሮ”</b> — ስለ AI ምንነትና እንዴት በዕለት ተዕለት ህይወትዎ በተግባር መጠቀም እንደሚችሉ ከመሠረቱ የሚያስተምር የተሟላ መጽሐፍ ነው።

በዚህ መጽሐፍ ውስጥ፦
• ባለ 131 ገጽ ተግባራዊ ዕውቀት ሙሉ በሙሉ በአማርኛ
• 27+ ኮፒ ተደርገው ወዲያውኑ የሚሠሩ ዝግጁ Prompts
• ለሥራ፣ ለትምህርት፣ ለCV/Job Search እና ለቢዝነስ የተዘጋጁ Workflows
• በስልክዎ ብቻ የሚተገበር፤ ምንም ዓይነት Coding ወይም የቴክኒክ ዳራ አይጠይቅም

<b>አሁኑኑ AIን ተረድተው ስራዎን ማቅለል ይጀምሩ!</b>

---
<i>💡 መጽሐፉን እንዴት ማግኘት ይችላሉ?</i>
• ወዲያውኑ ገዝተው ለማንበብ፦ «💚 ልግዛ · 549.00 ብር» የሚለውን ይጫኑ
• የይዘት ማውጫውንና ማሳያውን ለማየት፦ «👀 ውስጡን አሳየኝ» ይጫኑ
• ነፃ ሳምፕል ለማንበብ፦ «📄 ሳምፕል PDF ነፃ» ይጫኑ"""

    english = """<b>🚨 While others complete hours of work in minutes with AI, are you still wasting time guessing what to type?</b>

The problem isn't your capability - it's <i>not having a structured system to guide AI</i>.

📘 <b>“AI ከዜሮ”</b> is a complete, step-by-step book built to teach you exactly what AI is and how to use it for real-world tasks.

Inside this book:
• 131 practical pages written clearly in Amharic
• 27+ ready-to-use, copy-paste prompts that get instant results
• Complete AI frameworks for work, study, career growth, and business
• 100% mobile-friendly - zero coding or technical background required

<b>Stop guessing. Master AI and take control of your time today!</b>

---
<i>💡 How to proceed:</i>
• To get the complete book instantly: tap «💚 Get it · 549.00 Br»
• To preview the chapters and sample: tap «👀 Show me what's inside»
• To read the free sample: tap «📄 Free sample PDF»"""
    return amharic, english


def _buttons(*, buy_url: str, preview_url: str, sample_url: str) -> list[dict[str, str]]:
    return [
        {"key": "buy", "text": "💚 ልግዛ · 549.00 ብር", "url": buy_url},
        {"key": "preview", "text": "👀 ውስጡን አሳየኝ", "url": preview_url},
        {"key": "sample", "text": "📄 ሳምፕል PDF ነፃ", "url": sample_url},
    ]


def _buttons_en(*, buy_url: str, preview_url: str, sample_url: str) -> list[dict[str, str]]:
    return [
        {"key": "buy", "text": "💚 Get it · 549.00 Br", "url": buy_url},
        {"key": "preview", "text": "👀 Show me what's inside", "url": preview_url},
        {"key": "sample", "text": "📄 Free sample PDF", "url": sample_url},
    ]


def _callback_buttons() -> list[dict[str, str]]:
    return [
        {"key": "buy", "text": "💚 ልግዛ · 549.00 ብር", "callback_data": "retarget:action:buy"},
        {"key": "preview", "text": "👀 ውስጡን አሳየኝ", "callback_data": "retarget:action:preview"},
        {"key": "sample", "text": "📄 ሳምፕል PDF ነፃ", "callback_data": "retarget:action:sample"},
    ]


def _callback_buttons_en() -> list[dict[str, str]]:
    return [
        {"key": "buy", "text": "💚 Get it · 549.00 Br", "callback_data": "retarget:action:buy"},
        {"key": "preview", "text": "👀 Show me what's inside", "callback_data": "retarget:action:preview"},
        {"key": "sample", "text": "📄 Free sample PDF", "callback_data": "retarget:action:sample"},
    ]


def _preview(text: str, buttons: list[dict[str, str]], audience_count: int) -> None:
    print("\n" + "=" * 72)
    print("HIGH-INTENT RETARGETING PREVIEW")
    print("=" * 72)
    print(f"Audience: {audience_count} all active reachable bot users for {PRODUCT_SLUG}")
    print("Mode: text-only broadcast")
    print("\n" + text)
    print("\nButtons:")
    for button in buttons:
        print(f"  [{button['text']}] -> {button['url']}")
    print("=" * 72)


async def run(*, dry_run: bool) -> None:
    settings = get_settings()
    if not settings.admin_telegram_ids:
        raise ValueError("ADMIN_TELEGRAM_IDS must contain at least one authorized admin")
    db = Database(settings.database_url, settings.db_min_pool_size, settings.db_max_pool_size)
    await db.connect()
    try:
        service = MarketingService(db, settings)
        async with db.acquire() as conn:
            product = await conn.fetchrow(
                "SELECT id,slug,status,regular_price_br FROM products WHERE slug=$1 LIMIT 1",
                PRODUCT_SLUG,
            )
        if product is None or product["status"] != "active":
            raise LookupError(f"Active product not found: {PRODUCT_SLUG}")

        audience = normalize_audience({"kind": "everyone"})
        audience_count = await service.audience_count(audience.as_dict())
        am_text, en_text = retargeting_copy()

        urls = ["<created-on-launch>" for _ in range(3)]

        am_buttons = _buttons(buy_url=urls[0], preview_url=urls[1], sample_url=urls[2])
        en_buttons = _buttons_en(buy_url=urls[0], preview_url=urls[1], sample_url=urls[2])
        _preview(am_text, am_buttons, audience_count)
        print("\nENGLISH PREVIEW")
        print(en_text)
        print("\nButtons:")
        for button in en_buttons:
            print(f"  [{button['text']}] -> {button['url']}")

        if dry_run:
            print("\nDry run complete. No broadcast was created.")
            return
        if audience_count == 0:
            print("\nNo eligible high-intent users. No broadcast was created.")
            return
        if input("\nType LAUNCH to create and schedule this broadcast: ").strip() != "LAUNCH":
            print("Aborted. No broadcast was created.")
            return

        broadcast = await service.create_broadcast(
            admin_telegram_id=settings.admin_telegram_ids[0],
            data={
                "name": CAMPAIGN_NAME,
                "audience_definition": audience.as_dict(),
                "content_am": {"text": am_text, "buttons": _callback_buttons()},
                "content_en": {"text": en_text, "buttons": _callback_buttons_en()},
            },
        )
        scheduled = await service.schedule_broadcast(
            broadcast_id=UUID(str(broadcast["id"])),
            admin_telegram_id=settings.admin_telegram_ids[0],
            scheduled_at=datetime.now(UTC),
        )
        print(f"\nScheduled broadcast {broadcast['id']} for {scheduled['audience_snapshot_count']} users.")
    finally:
        await db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Launch the high-intent text-only retargeting broadcast")
    parser.add_argument("--dry-run", action="store_true", help="Preview copy and audience without creating a broadcast")
    args = parser.parse_args()
    asyncio.run(run(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
