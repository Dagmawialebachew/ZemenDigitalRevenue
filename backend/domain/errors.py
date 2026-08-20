class DomainError(ValueError):
    """Base class for business-rule violations."""


class InvalidStateTransition(DomainError):
    pass


class InvalidPricing(DomainError):
    pass


class CommissionNotAllowed(DomainError):
    pass
