from __future__ import annotations

# The owner has manually confirmed that the product passed this paid-reader
# milestone. Keep the conservative milestone until the paid-order total reaches
# 50, then derive future public milestones from verified paid orders.
EARLY_PURCHASE_MILESTONE = 33
NEXT_PURCHASE_MILESTONE = 50


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
