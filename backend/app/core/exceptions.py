"""Domain-level exceptions. API routers translate these into HTTP responses
(see api/routers/*.py) — the service layer never imports FastAPI/HTTPException,
keeping business logic framework-agnostic and independently testable."""


class DomainError(Exception):
    """Base class for all expected, business-rule-driven failures."""


class AuthenticationError(DomainError):
    """Bad credentials or invalid/expired token."""


class AuthorizationError(DomainError):
    """Authenticated, but not allowed to touch this resource."""


class NotFoundError(DomainError):
    """Requested entity does not exist (or isn't owned by this caller)."""


class ValidationError(DomainError):
    """Caller-supplied input failed a business-rule check."""


class IngestionError(DomainError):
    """A document could not be parsed/chunked/embedded/indexed."""
