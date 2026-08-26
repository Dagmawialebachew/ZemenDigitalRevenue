"""
299 Br Today-Only Recovery Campaign Launcher
=============================================
Creates discount rule, bulk customer_offers, tracking link, uploads promo image,
creates 4 broadcasts (high-intent + all non-buyers + 2 drip reminders), and
schedules them with admin preview + confirmation before dispatch.

Usage:
    python scripts/launch_recovery_campaign.py --image path/to/promo.jpg
"""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import asyncio
import mimetypes
from datetime import UTC, datetime, timedelta
from textwrap import dedent
from uuid import UUID

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from backend.core.config import get_settings
from backend.db.pool import Database
from backend.services.marketing import MarketingService


# ──────────────────────────  CAMPAIGN COPY  ──────────────────────────

def blast_1a_high_intent() -> tuple[dict, dict]:
    """High-intent non-buyers: 'You were THIS close'."""
    am = {
        "text": dedent("""\
            {first_name}፣ ያኔ ለመግዛት ተቃርበው ነበር...

            ዛሬ ልዩ ነገር ስላለ ነው 👇

            AI ከዜሮ — 549 ብር ➜ 299 ብር ብቻ!

            ይህ ዋጋ ዛሬ ማታ 6 ሰአት ላይ ያበቃል። ከዚያ በኋላ 549 ብር ይመለሳል። ልዩ ሁኔታ የለም።

            ቀድሞ ነው ጊዜን ያሳለፉት። ቀድሞ ነው ያዩት። አሁን ውሳኔ ብቻ ይቀራል።

            ከ6 ወር በኋላ ምንም ካልተለወጠ — ማለትም ዛሬ ያመለጠ ማለት ነው።""").strip(),
        "buttons": [{"key": "buy", "text": "\U0001f525 አሁን ይግዙ — 299 ብር", "url": "__BOT_URL__"}],
    }
    en = {
        "text": dedent("""\
            {first_name}, you were SO close to getting this...

            Today something special just dropped 👇

            AI From Zero — 549 Br ➜ Only 299 Br!

            This price DIES tonight at midnight. After that, it's 549 Br. No exceptions.

            You already spent the time. You already saw the value. The only thing missing is your decision.

            6 months from now, if nothing changed — it's because of this moment right here.""").strip(),
        "buttons": [{"key": "buy", "text": "\U0001f525 Get It Now — 299 Br", "url": "__BOT_URL__"}],
    }
    return am, en


def blast_1b_all_non_buyers() -> tuple[dict, dict]:
    """All non-buyers: FOMO + social proof."""
    am = {
        "text": dedent("""\
            {first_name}፣ ይህን ማወቅ አለብዎት...

            በዚህ ሳምንት ብቻ 52+ ሰዎች AI ከዜሮ ገዝተዋል። ከእነሱ ጋር ለምን አልተቀላቀሉም?

            ዛሬ ብቻ — 299 ብር (ከ549 ብር ይልቅ)

            ሁሉም ሰው AI እየተማረ ነው። ኢትዮጵያ ውስጥ AI ለሥራ፣ ለንግድ፣ ለትምህርት — ሁሉም እየተጠቀመ ነው።

            ጥያቄው ይህ ነው: ይቀራሉ ወይስ ይቀላቀላሉ?

            ዋጋው ዛሬ ማታ 6 ሰአት ላይ ያበቃል ⏰""").strip(),
        "buttons": [{"key": "buy", "text": "\U0001f525 አሁን ተቀላቀሉ — 299 ብር", "url": "__BOT_URL__"}],
    }
    en = {
        "text": dedent("""\
            {first_name}, you need to know this...

            52+ people bought AI From Zero just this week. Why aren't you one of them?

            TODAY ONLY — 299 Br (instead of 549 Br)

            Everyone is learning AI. In Ethiopia, AI for work, business, education — everyone is using it now.

            The question is: are you going to be left behind, or are you joining?

            Price expires tonight at midnight ⏰""").strip(),
        "buttons": [{"key": "buy", "text": "\U0001f525 Join Now — 299 Br", "url": "__BOT_URL__"}],
    }
    return am, en


def blast_2_reminder() -> tuple[dict, dict]:
    """Reminder: 'Hours left'."""
    am = {
        "text": dedent("""\
            {first_name}... ገና 4 ሰዓት ብቻ ይቀራል ⏰

            AI ከዜሮ — 299 ብር

            ይህ ቀልድ አይደለም። ማታ 6 ሰአት = 549 ብር ይመለሳል።

            ቀድሞ ይጠቀሙ 👇""").strip(),
        "buttons": [{"key": "buy", "text": "⏰ 299 ብር — ከማለፉ በፊት", "url": "__BOT_URL__"}],
    }
    en = {
        "text": dedent("""\
            {first_name}... Only 4 hours left ⏰

            AI From Zero — 299 Br

            This is not a joke. Midnight = back to 549 Br.

            Get it before it's gone 👇""").strip(),
        "buttons": [{"key": "buy", "text": "⏰ 299 Br — Before It's Gone", "url": "__BOT_URL__"}],
    }
    return am, en


def blast_3_final() -> tuple[dict, dict]:
    """Final warning: '1 hour left'."""
    am = {
        "text": dedent("""\
            ⚠️ {first_name} — 1 ሰዓት ብቻ!

            299 ብር ➜ ማታ 6 ሰአት ላይ ያበቃል

            ከዚያ 549 ብር ይሆናል። ያ ውሳኔ የእርስዎ ነው።

            የመጨረሻ ዕድል 👇""").strip(),
        "buttons": [{"key": "buy", "text": "\U0001f6a8 የመጨረሻ ዕድል — 299 ብር", "url": "__BOT_URL__"}],
    }
    en = {
        "text": dedent("""\
            ⚠️ {first_name} — 1 HOUR LEFT!

            299 Br ➜ EXPIRES at midnight

            After that it's 549 Br. That decision is yours.

            Last chance 👇""").strip(),
        "buttons": [{"key": "buy", "text": "\U0001f6a8 Last Chance — 299 Br", "url": "__BOT_URL__"}],
    }
    return am, en


# ──────────────────────────  HELPERS  ──────────────────────────

def _inject_media(content: dict, media: dict) -> dict:
    content["media"] = media
    return content


def _inject_url(content: dict, url: str) -> dict:
    for btn in content.get("buttons", []):
        if btn.get("url") == "__BOT_URL__":
            btn["url"] = url
    return content


def _preview_content(label: str, content: dict) -> str:
    text = content.get("text", "")
    buttons = content.get("buttons", [])
    media = content.get("media", {})
    lines = [f"\n{'='*60}", f"  {label}", f"{'='*60}"]
    if media:
        lines.append(f"  [IMAGE] type={media.get('type', 'none')}")
    lines.append("")
    for line in text.split("\n"):
        lines.append(f"  {line}")
    lines.append("")
    for btn in buttons:
        lines.append(f"  [ {btn['text']} ] -> {btn['url'][:60]}...")
    return "\n".join(lines)


# ──────────────────────────  MAIN  ──────────────────────────

async def run(image_path: str | None) -> None:
    settings = get_settings()
    db = Database(settings.database_url, settings.db_min_pool_size, settings.db_max_pool_size)
    await db.connect()

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    svc = MarketingService(db, settings, bot)

    try:
        admin_tg_id = settings.admin_telegram_ids
        print("\n\U0001f525 ZEMEN 299 Br Today-Only Recovery Campaign Launcher")
        print("=" * 60)

        # -- Step 1: Find the product --
        async with db.connection() as conn:
            product = await conn.fetchrow(
                "SELECT p.id,p.slug,p.regular_price_br,p.recovery_price_br,p.discounts_enabled,"
                "COALESCE(am.title,en.title,p.slug) AS title "
                "FROM products p "
                "LEFT JOIN product_translations am ON am.product_id=p.id AND am.language='am' "
                "LEFT JOIN product_translations en ON en.product_id=p.id AND en.language='en' "
                "WHERE p.slug='ai-kezero' AND p.status='active' LIMIT 1"
            )
        if not product:
            print("ERROR: Product 'ai-kezero' not found or inactive. Aborting.")
            return

        product_id = str(product["id"])
        print(f"\nProduct: {product['title']} (slug={product['slug']})")
        print(f"   Regular price: {product['regular_price_br']} Br")
        print(f"   Discounts enabled: {product['discounts_enabled']}")

        if not product["discounts_enabled"]:
            print("\n   Enabling discounts on product...")
            async with db.transaction() as conn:
                await conn.execute("UPDATE products SET discounts_enabled=TRUE WHERE id=$1", product["id"])
            print("   Done.")

        # -- Step 2: Calculate expiry (midnight EAT = UTC+3) --
        now_utc = datetime.now(UTC)
        eat_offset = timedelta(hours=3)
        now_eat = now_utc + eat_offset
        midnight_eat = now_eat.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        midnight_utc = midnight_eat - eat_offset
        seconds_until_midnight = int((midnight_utc - now_utc).total_seconds())
        if seconds_until_midnight <= 0:
            print("ERROR: It's already past midnight EAT. Campaign deadline has passed.")
            return

        hours_left = seconds_until_midnight / 3600
        print(f"\nDeadline: Midnight EAT ({midnight_utc.isoformat()})")
        print(f"   {hours_left:.1f} hours remaining ({seconds_until_midnight}s)")

        # -- Step 3: Create discount rule --
        print("\nCreating discount rule (299 Br, campaign type)...")
        rule = await svc.create_discount_rule(
            admin_telegram_id=admin_tg_id,
            data={
                "product_id": product_id,
                "name": "Today-Only 299 Br Flash Recovery",
                "rule_type": "campaign",
                "target_price_br": "299.00",
                "expires_after_seconds": seconds_until_midnight,
                "is_active": True,
                "require_no_pending_payment": True,
                "minimum_intent_score": 0,
            },
        )
        rule_id = UUID(str(rule["id"]))
        print(f"   Discount rule created: {rule_id}")

        # -- Step 4: Bulk-create customer offers --
        print("\nLaunching bulk campaign offers for all non-buyers...")
        result = await svc.launch_campaign_offers(rule_id=rule_id, admin_telegram_id=admin_tg_id)
        print(f"   Created {result['created']} offers at {result['offer_price_br']} Br")
        print(f"   Offers expire at: {result['expires_at']}")

        if int(result["created"]) == 0:
            print("WARNING: No eligible non-buyers found. Check your database.")
            return

        # -- Step 5: Create tracking link --
        print("\nCreating tracking link...")
        link = await svc.create_tracking_link(
            admin_telegram_id=admin_tg_id,
            data={
                "name": "299 Br Recovery Campaign Aug 26",
                "product_id": product_id,
                "platform": "telegram",
                "campaign": "recovery-299-aug26",
                "creative": "broadcast-image",
                "angle": "today-only-flash-sale",
            },
        )
        bot_url = link.get("bot_url", "")
        print(f"   Tracking link: {bot_url}")

        # -- Step 6: Upload promo image --
        media = None
        if image_path:
            img = Path(image_path)
            if img.exists():
                print(f"\nUploading promo image: {img.name}...")
                content_type = mimetypes.guess_type(str(img))[0] or "image/jpeg"
                media = await svc.upload_broadcast_media(
                    filename=img.name,
                    content_type=content_type,
                    data=img.read_bytes(),
                )
                print(f"   Uploaded: type={media['type']}, file_id={media['file_id'][:30]}...")
            else:
                print(f"   WARNING: Image not found at {img}, continuing without media.")

        # -- Step 7: Build all broadcast content --
        b1a_am, b1a_en = blast_1a_high_intent()
        b1b_am, b1b_en = blast_1b_all_non_buyers()
        b2_am, b2_en = blast_2_reminder()
        b3_am, b3_en = blast_3_final()

        all_content = [
            (b1a_am, b1a_en), (b1b_am, b1b_en),
            (b2_am, b2_en), (b3_am, b3_en),
        ]

        for am, en in all_content:
            _inject_url(am, bot_url)
            _inject_url(en, bot_url)
            if media:
                _inject_media(am, media)
                _inject_media(en, media)

        # -- Step 8: Preview for admin --
        print("\n" + "=" * 60)
        print("  BROADCAST PREVIEW — Review before dispatch")
        print("=" * 60)

        labels = [
            ("BLAST 1A — High Intent (AM)", b1a_am),
            ("BLAST 1A — High Intent (EN)", b1a_en),
            ("BLAST 1B — All Non-Buyers (AM)", b1b_am),
            ("BLAST 1B — All Non-Buyers (EN)", b1b_en),
            ("BLAST 2 — Reminder (AM)", b2_am),
            ("BLAST 2 — Reminder (EN)", b2_en),
            ("BLAST 3 — Final Warning (AM)", b3_am),
            ("BLAST 3 — Final Warning (EN)", b3_en),
        ]
        for label, content in labels:
            print(_preview_content(label, content))

        print("\n" + "=" * 60)
        print(f"  Campaign Summary")
        print(f"  Offers created: {result['created']}")
        print(f"  Price: 549 -> 299 Br")
        print(f"  Deadline: Midnight EAT ({hours_left:.1f}h remaining)")
        print(f"  Drip: 4 broadcasts (1A now -> 1B +5m -> 2 +4h -> 3 +7h)")
        print(f"  Media: {'Yes (' + media['type'] + ')' if media else 'No image'}")
        print("=" * 60)

        # -- Step 9: Admin confirmation --
        confirm = input("\nReady to launch? Type 'LAUNCH' to confirm: ").strip()
        if confirm != "LAUNCH":
            print("Aborted. No broadcasts created.")
            return

        # -- Step 10: Create broadcasts --
        print("\nCreating broadcasts...")

        b1a = await svc.create_broadcast(
            admin_telegram_id=admin_tg_id,
            data={
                "name": "299 Recovery — Blast 1A High Intent",
                "audience_definition": {"kind": "high_intent", "product_id": product_id},
                "content_am": b1a_am,
                "content_en": b1a_en,
            },
        )
        print(f"   Blast 1A created: {b1a['id']}")

        b1b = await svc.create_broadcast(
            admin_telegram_id=admin_tg_id,
            data={
                "name": "299 Recovery — Blast 1B All Non-Buyers",
                "audience_definition": {"kind": "non_buyers", "product_id": product_id},
                "content_am": b1b_am,
                "content_en": b1b_en,
            },
        )
        print(f"   Blast 1B created: {b1b['id']}")

        b2 = await svc.create_broadcast(
            admin_telegram_id=admin_tg_id,
            data={
                "name": "299 Recovery — Blast 2 Reminder",
                "audience_definition": {"kind": "non_buyers", "product_id": product_id},
                "content_am": b2_am,
                "content_en": b2_en,
            },
        )
        print(f"   Blast 2 created: {b2['id']}")

        b3 = await svc.create_broadcast(
            admin_telegram_id=admin_tg_id,
            data={
                "name": "299 Recovery — Blast 3 Final Warning",
                "audience_definition": {"kind": "non_buyers", "product_id": product_id},
                "content_am": b3_am,
                "content_en": b3_en,
            },
        )
        print(f"   Blast 3 created: {b3['id']}")

        # -- Step 11: Schedule broadcasts --
        now = datetime.now(UTC)

        await svc.schedule_broadcast(
            broadcast_id=UUID(str(b1a["id"])),
            admin_telegram_id=admin_tg_id,
            scheduled_at=now,
        )
        print(f"\n   Blast 1A scheduled: NOW")

        await svc.schedule_broadcast(
            broadcast_id=UUID(str(b1b["id"])),
            admin_telegram_id=admin_tg_id,
            scheduled_at=now + timedelta(minutes=5),
        )
        print(f"   Blast 1B scheduled: +5 min")

        b2_time = now + timedelta(hours=4)
        if b2_time < midnight_utc:
            await svc.schedule_broadcast(
                broadcast_id=UUID(str(b2["id"])),
                admin_telegram_id=admin_tg_id,
                scheduled_at=b2_time,
            )
            print(f"   Blast 2 scheduled: +4h ({b2_time.isoformat()})")
        else:
            print(f"   Blast 2 skipped (would be past midnight)")

        b3_time = min(now + timedelta(hours=7), midnight_utc - timedelta(hours=1))
        if b3_time > now + timedelta(minutes=30) and b3_time < midnight_utc:
            await svc.schedule_broadcast(
                broadcast_id=UUID(str(b3["id"])),
                admin_telegram_id=admin_tg_id,
                scheduled_at=b3_time,
            )
            print(f"   Blast 3 scheduled: {b3_time.isoformat()}")
        else:
            print(f"   Blast 3 skipped (not enough time before midnight)")

        print("\n" + "=" * 60)
        print("  CAMPAIGN LAUNCHED SUCCESSFULLY")
        print("=" * 60)
        print(f"  Offers: {result['created']} users at 299 Br")
        print(f"  Broadcasts: created and scheduled")
        print(f"  Tracking: {bot_url}")
        print(f"  Deadline: Midnight EAT ({midnight_utc.isoformat()})")
        print("=" * 60)

    finally:
        await bot.session.close()
        await db.close()


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Launch 299 Br Recovery Campaign")
    parser.add_argument("--image", default=None, help="Path to promo image (jpg/png)")
    args = parser.parse_args()
    asyncio.run(run(args.image))


if __name__ == "__main__":
    main()
