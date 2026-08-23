from __future__ import annotations

from typing import TypedDict

# The owner has manually confirmed that the product passed this paid-reader
# milestone. Keep the conservative milestone until the paid-order total reaches
# 50, then derive future public milestones from verified paid orders.
EARLY_PURCHASE_MILESTONE = 33
NEXT_PURCHASE_MILESTONE = 50


class ReaderTestimonial(TypedDict):
    username: str
    text: str


_TESTIMONIALS: dict[str, tuple[ReaderTestimonial, ...]] = {
    "en": (
        {"username": "@Ber***sg", "text": "Simple and practical."},
        {"username": "@Nat***a2", "text": "Clear and very useful."},
        {"username": "@Ale***34", "text": "Worth reading."},
        {"username": "@Ele***01", "text": "Easy to follow."},
    ),
    "am": (
        {"username": "@Ber***sg", "text": "ቀላልና ተግባራዊ ነው።"},
        {"username": "@Nat***a2", "text": "ግልጽና በጣም ጠቃሚ ነው።"},
        {"username": "@Ale***34", "text": "ማንበብ ዋጋ አለው።"},
        {"username": "@Ele***01", "text": "ለመከተል ቀላል ነው።"},
    ),
}


def purchase_milestone(actual_paid_orders: int) -> int:
    """Return a conservative public milestone, never a precise volatile count."""
    if actual_paid_orders < NEXT_PURCHASE_MILESTONE:
        return EARLY_PURCHASE_MILESTONE
    return (actual_paid_orders // 10) * 10


def community_milestone(actual_members: int) -> int:
    """Round community size down so the public claim never exceeds the real total."""
    if actual_members < 10:
        return max(0, actual_members)
    return (actual_members // 10) * 10


def reader_testimonials(language: str) -> list[ReaderTestimonial]:
    selected = _TESTIMONIALS["en" if language == "en" else "am"]
    return [dict(item) for item in selected]
