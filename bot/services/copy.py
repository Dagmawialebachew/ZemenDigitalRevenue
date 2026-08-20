from __future__ import annotations

from dataclasses import dataclass

from backend.services.customer_entry import CustomerEntryContext


@dataclass(frozen=True, slots=True)
class EntryCopy:
    text: str
    rich_markdown: str


def language_prompt(entry: CustomerEntryContext) -> EntryCopy:
    product_line_am = (
        f"\n\n📦 **{entry.focus_product_title}** ለማየት ነው የመጡት — ተረድቻለሁ።"
        if entry.focus_product_title else ""
    )
    product_line_en = (
        f"\n\n📦 You came for **{entry.focus_product_title}** — got it."
        if entry.focus_product_title else ""
    )
    return EntryCopy(
        text=(
            "👋 እንኳን ወደ Zemen Digital በደህና መጡ!\n\n"
            "ከመጀመራችን በፊት በየትኛው ቋንቋ እንቀጥል?"
            + product_line_am.replace("**", "")
            + "\n\n🇬🇧 English is available too."
        ),
        rich_markdown=(
            "# 👋 Zemen Digital\n\n"
            "ከመጀመራችን በፊት **በየትኛው ቋንቋ እንቀጥል?**"
            + product_line_am
            + "\n\n🇬🇧 English is available too."
        ),
    )



def _angle_hint(entry: CustomerEntryContext, *, language: str) -> str:
    angle = (entry.angle or "").strip().lower()
    if angle == "beginner_confusion":
        if language == "en":
            return "\n\n👀 You came from the ‘I opened ChatGPT… now what?’ angle — I’ll keep that context in mind."
        return "\n\n👀 ChatGPTን ከፍተው ‘አሁን ምን ልጠይቀው?’ ከሚለው ችግር መጥተዋል — ይሄን አልረሳውም።"
    if angle == "work_study_business":
        if language == "en":
            return "\n\n💼📚📈 You came for practical work, study or business use — so I’ll keep this practical."
        return "\n\n💼📚📈 ለስራ፣ ለትምህርት ወይም ለንግድ ተግባራዊ አጠቃቀም ነው የመጡት — ንግግሩንም በዚያ ላይ እናቆየዋለን።"
    return ""

def after_language(entry: CustomerEntryContext, *, language: str) -> EntryCopy:
    title = entry.focus_product_title
    if language == "en":
        product = f"\n\n📦 **{title}** is already open for you." if title else ""
        angle_hint = _angle_hint(entry, language=language)
        return EntryCopy(
            text=(
                f"✅ Perfect, {entry.first_name}. We'll continue in English."
                + product.replace("**", "")
                + angle_hint
                + "\n\nI’ll ask a few quick questions so I can show you the parts that actually fit you — no long form. 👀"
            ),
            rich_markdown=(
                f"## ✅ Perfect, {entry.first_name}\n\nWe'll continue in **English**."
                + product
                + angle_hint
                + "\n\nI’ll ask a few quick questions so I can show you what actually fits you — **no long form**. 👀"
            ),
        )
    product = f"\n\n📦 **{title}** ለእርስዎ ተዘጋጅቷል።" if title else ""
    angle_hint = _angle_hint(entry, language=language)
    return EntryCopy(
        text=(
            f"✅ ጥሩ {entry.first_name}፣ በአማርኛ እንቀጥላለን።"
            + product.replace("**", "")
            + angle_hint
            + "\n\nረጅም form አይደለም 😄 ለእርስዎ ትክክለኛውን ነገር እንዳሳይዎ ጥቂት ፈጣን ጥያቄዎች ብቻ እጠይቃለሁ።"
        ),
        rich_markdown=(
            f"## ✅ ጥሩ {entry.first_name}\n\nበ**አማርኛ** እንቀጥላለን።"
            + product
            + angle_hint
            + "\n\nረጅም form አይደለም 😄 ለእርስዎ ትክክለኛውን ነገር እንዳሳይዎ **ጥቂት ፈጣን ጥያቄዎች** ብቻ እጠይቃለሁ።"
        ),
    )


def returning_prompt(entry: CustomerEntryContext) -> EntryCopy:
    title = entry.focus_product_title
    if entry.language_for_copy == "en":
        target = f"\n\n📦 **{title}** is ready to continue." if title else ""
        return EntryCopy(
            text=f"👋 Welcome back, {entry.first_name}." + target.replace("**", ""),
            rich_markdown=f"# 👋 Welcome back, {entry.first_name}" + target,
        )
    target = f"\n\n📦 **{title}** ከቆሙበት ለመቀጠል ዝግጁ ነው።" if title else ""
    return EntryCopy(
        text=f"👋 እንኳን በድጋሚ መጡ {entry.first_name}።" + target.replace("**", ""),
        rich_markdown=f"# 👋 እንኳን በድጋሚ መጡ {entry.first_name}" + target,
    )
