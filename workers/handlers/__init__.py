from workers.handlers.ops import notify_ops_handler
from workers.handlers.payments import (
    payment_drip_reminder_handler,
    payment_review_handler,
    product_delivery_handler,
    user_notify_handler,
)
from workers.handlers.operations import maintenance_handler, ops_alert_handler, support_case_handler
from workers.handlers.system import noop_handler
from workers.handlers.marketing import (
    automation_trigger_handler, automation_step_handler, automation_message_handler,
    offer_expire_handler, marketing_maintenance_handler, broadcast_dispatch_handler, broadcast_send_handler,
)
from workers.registry import JobRegistry


def build_registry() -> JobRegistry:
    registry = JobRegistry()
    registry.register("system.noop", noop_handler)
    registry.register("telegram.ops.notify", notify_ops_handler)
    registry.register("telegram.ops.payment_review", payment_review_handler)
    registry.register("telegram.user.notify", user_notify_handler)
    registry.register("telegram.delivery.product", product_delivery_handler)
    registry.register("payment.drip.reminder_15m", payment_drip_reminder_handler)
    registry.register("payment.drip.reminder_2h", payment_drip_reminder_handler)
    registry.register("payment.drip.reminder_24h", payment_drip_reminder_handler)
    registry.register("operations.maintenance", maintenance_handler)
    registry.register("telegram.ops.alert", ops_alert_handler)
    registry.register("telegram.ops.support_case", support_case_handler)
    registry.register("marketing.automation.trigger", automation_trigger_handler)
    registry.register("marketing.automation.step", automation_step_handler)
    registry.register("marketing.automation.message", automation_message_handler)
    registry.register("marketing.offer.expire", offer_expire_handler)
    registry.register("marketing.maintenance", marketing_maintenance_handler)
    registry.register("marketing.broadcast.dispatch", broadcast_dispatch_handler)
    registry.register("marketing.broadcast.send", broadcast_send_handler)
    return registry


__all__ = ["build_registry"]
