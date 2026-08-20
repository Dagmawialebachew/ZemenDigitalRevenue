from enum import StrEnum


class Language(StrEnum):
    AMHARIC = "am"
    ENGLISH = "en"


class UserRole(StrEnum):
    STUDENT = "student"
    PROFESSIONAL = "professional"
    JOB_SEEKER = "job_seeker"
    BUSINESS_OWNER = "business_owner"
    OTHER = "other"


class AIExperience(StrEnum):
    NEVER_USED = "never_used"
    TRIED_CONFUSED = "tried_confused"
    OCCASIONAL = "occasional"
    FREQUENT = "frequent"


class MainGoal(StrEnum):
    LEARN_FASTER = "learn_faster"
    WORK_SMARTER = "work_smarter"
    GROW_BUSINESS = "grow_business"
    FIND_OPPORTUNITIES = "find_opportunities"
    SAVE_TIME = "save_time"
    OTHER = "other"


class MainObstacle(StrEnum):
    DONT_KNOW_WHAT_TO_ASK = "dont_know_what_to_ask"
    POOR_ANSWERS = "poor_answers"
    AMHARIC_UNCERTAINTY = "amharic_uncertainty"
    DONT_KNOW_USE_CASES = "dont_know_use_cases"
    NEEDS_PRACTICAL_USE = "needs_practical_use"
    OTHER = "other"


class CustomerStage(StrEnum):
    NEW = "new"
    ONBOARDING = "onboarding"
    EXPLORING = "exploring"
    PRODUCT_INTERESTED = "product_interested"
    HIGH_INTENT = "high_intent"
    BUY_CLICKED = "buy_clicked"
    AWAITING_PAYMENT = "awaiting_payment"
    PROOF_SUBMITTED = "proof_submitted"
    PAYMENT_REJECTED = "payment_rejected"
    CUSTOMER = "customer"
    REPEAT_CUSTOMER = "repeat_customer"


class ProductStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    HIDDEN = "hidden"
    ARCHIVED = "archived"


class PricingType(StrEnum):
    REGULAR = "regular"
    RECOVERY = "recovery"
    MANUAL_DISCOUNT = "manual_discount"


class OfferStatus(StrEnum):
    SCHEDULED = "scheduled"
    AVAILABLE = "available"
    REDEEMED = "redeemed"
    EXPIRED = "expired"
    REVOKED = "revoked"


class OrderStatus(StrEnum):
    CREATED = "created"
    AWAITING_PAYMENT = "awaiting_payment"
    PROOF_SUBMITTED = "proof_submitted"
    UNDER_REVIEW = "under_review"
    NEEDS_NEW_PROOF = "needs_new_proof"
    PAID = "paid"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    REFUNDED = "refunded"


class PaymentStatus(StrEnum):
    AWAITING_PROOF = "awaiting_proof"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    FLAGGED = "flagged"
    CANCELLED = "cancelled"


class PaymentMethod(StrEnum):
    CBE = "cbe"
    TELEBIRR = "telebirr"
    OTHER_MANUAL = "other_manual"
    TELEGRAM_STARS = "telegram_stars"
    FUTURE_PROVIDER = "future_provider"


class PaymentRejectReason(StrEnum):
    WRONG_AMOUNT = "wrong_amount"
    WRONG_RECEIVER = "wrong_receiver"
    UNCLEAR_SCREENSHOT = "unclear_screenshot"
    OLD_TRANSACTION = "old_transaction"
    DUPLICATE_RECEIPT = "duplicate_receipt"
    TRANSACTION_NOT_FOUND = "transaction_not_found"
    OTHER = "other"


class DeliveryStatus(StrEnum):
    PENDING = "pending"
    QUEUED = "queued"
    DELIVERED = "delivered"
    FAILED = "failed"
    REVOKED = "revoked"


class CommissionStatus(StrEnum):
    PENDING = "pending"
    AVAILABLE = "available"
    PAID = "paid"
    VOID = "void"


class BroadcastStatus(StrEnum):
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    SENDING = "sending"
    SENT = "sent"
    CANCELLED = "cancelled"
    FAILED = "failed"


class AutomationRunStatus(StrEnum):
    ACTIVE = "active"
    WAITING = "waiting"
    COMPLETED = "completed"
    STOPPED = "stopped"
    FAILED = "failed"


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
