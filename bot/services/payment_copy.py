from __future__ import annotations

from html import escape
from urllib.parse import urlencode, urlsplit, urlunsplit, parse_qsl

from backend.core.config import Settings
from backend.services.payments import CheckoutResult, PaymentResume


def money(value: object) -> str:
    text = f"{float(value):,.2f}"
    return text[:-3] if text.endswith(".00") else text


def checkout_intro(checkout: CheckoutResult, *, language: str) -> str:
    amount = money(checkout.total_due_br)
    if language == "en":
        discount = (
            f"\n🏷 <b>Recovery offer applied:</b> {amount} Br\n🤝 Referral commission: 0 Br on discounted orders."
            if checkout.pricing_type != "regular"
            else ""
        )
        return (
            f"💳 <b>Your order is ready</b>\n\n"
            f"📦 {escape(checkout.product_title)}\n"
            f"💰 <b>{amount} Br</b>\n"
            f"🧾 <code>{escape(checkout.public_id)}</code>"
            f"{discount}\n\nChoose how you'd like to pay 👇"
        )
    discount = (
        f"\n🏷 <b>Recovery offer ተግብሯል:</b> {amount} ብር\n🤝 Discount ባለው ግዢ commission = 0 ብር።"
        if checkout.pricing_type != "regular"
        else ""
    )
    return (
        f"💳 <b>ትዕዛዝዎ ዝግጁ ነው</b>\n\n"
        f"📦 {escape(checkout.product_title)}\n"
        f"💰 <b>{amount} ብር</b>\n"
        f"🧾 <code>{escape(checkout.public_id)}</code>"
        f"{discount}\n\nየክፍያ መንገድዎን ይምረጡ 👇"
    )


def resume_text(resume: PaymentResume) -> str:
    amount = money(resume.total_due_br)
    if resume.language == "en":
        if resume.payment_status in {"pending_review", "flagged"}:
            return (
                f"🔎 <b>Your payment is under review</b>\n\n📦 {escape(resume.product_title)}\n"
                f"💰 {amount} Br\n🧾 <code>{escape(resume.order_public_id)}</code>\n\n"
                "We'll message you here as soon as it is reviewed. ✅"
            )
        if resume.payment_status == "rejected":
            reason = (
                f"\n<b>Reason:</b> {escape(resume.rejection_reason)}\n"
                if resume.rejection_reason else ""
            )
            return (
                f"📸 <b>We need a new payment screenshot</b>\n\n📦 {escape(resume.product_title)}\n"
                f"{reason}"
                "Send the replacement screenshot directly in this chat."
            )
        return checkout_intro_from_resume(resume)
    if resume.payment_status in {"pending_review", "flagged"}:
        return (
            f"🔎 <b>ክፍያዎ በማረጋገጥ ላይ ነው</b>\n\n📦 {escape(resume.product_title)}\n"
            f"💰 {amount} ብር\n🧾 <code>{escape(resume.order_public_id)}</code>\n\n"
            "ሲረጋገጥ እዚሁ እናሳውቅዎታለን። ✅"
        )
    if resume.payment_status == "rejected":
        reason = (
            f"\n<b>ምክንያት:</b> {escape(resume.rejection_reason)}\n"
            if resume.rejection_reason else ""
        )
        return (
            f"📸 <b>አዲስ payment screenshot እንፈልጋለን</b>\n\n📦 {escape(resume.product_title)}\n"
            f"{reason}"
            "አዲሱን screenshot በቀጥታ እዚህ chat ይላኩ።"
        )
    return checkout_intro_from_resume(resume)


def checkout_intro_from_resume(resume: PaymentResume) -> str:
    amount = money(resume.total_due_br)
    if resume.language == "en":
        return (
            f"💳 <b>Continue your order</b>\n\n📦 {escape(resume.product_title)}\n"
            f"💰 <b>{amount} Br</b>\n🧾 <code>{escape(resume.order_public_id)}</code>\n\n"
            "Choose your payment method 👇"
        )
    return (
        f"💳 <b>ትዕዛዝዎን ይቀጥሉ</b>\n\n📦 {escape(resume.product_title)}\n"
        f"💰 <b>{amount} ብር</b>\n🧾 <code>{escape(resume.order_public_id)}</code>\n\n"
        "የክፍያ መንገድዎን ይምረጡ 👇"
    )


def payment_instructions(
    *,
    resume: PaymentResume,
    settings: Settings,
) -> tuple[str, str]:
    amount = money(resume.total_due_br)
    method = resume.payment_method
    if method == "cbe":
        destination = settings.cbe_account_number.strip()
        name = settings.cbe_account_name.strip() or "Zemen Digital"
        label = "Commercial Bank of Ethiopia"
    elif method == "telebirr":
        destination = settings.telebirr_number.strip()
        name = settings.telebirr_account_name.strip() or "Zemen Digital"
        label = "Telebirr"
    else:
        raise ValueError("payment method is not configured")
    if not destination:
        raise ValueError(f"{method} destination is not configured")

    if resume.language == "en":
        text = (
            f"💳 <b>{escape(label)}</b>\n\n"
            f"👤 {escape(name)}\n"
            f"🔢 <code>{escape(destination)}</code>\n"
            f"💰 <b>{amount} Br</b>\n"
            f"🧾 Order: <code>{escape(resume.order_public_id)}</code>\n\n"
            "After paying, tap <b>✅ I've Paid</b> and send the receipt screenshot here. 📸"
        )
    else:
        text = (
            f"💳 <b>{escape(label)}</b>\n\n"
            f"👤 {escape(name)}\n"
            f"🔢 <code>{escape(destination)}</code>\n"
            f"💰 <b>{amount} ብር</b>\n"
            f"🧾 Order: <code>{escape(resume.order_public_id)}</code>\n\n"
            "ክፍያውን ከፍለው <b>✅ ከፍያለሁ</b> ይጫኑ፤ ከዚያ receipt screenshot እዚሁ ይላኩ። 📸"
        )
    return text, destination


def external_checkout_url(base_url: str, order_public_id: str) -> str:
    parts = urlsplit(base_url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["order"] = order_public_id
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
