from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .readiness import Blocker


class TariffCoverageError(ValueError):
    """A tariff whose bands leave a gap in the week, or overlap."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class BandNotFound(LookupError):
    """No band covers the given moment. Unreachable when coverage is validated."""


class InvalidRate(ValueError):
    pass


class InvalidPolicy(ValueError):
    pass


class InvalidPeriodValue(ValueError):
    def __init__(self, value: str) -> None:
        super().__init__(value)
        self.value = value


class PeriodNotFound(LookupError):
    pass


class SiteNotFound(LookupError):
    pass


class BillingForbidden(PermissionError):
    pass


class InvoiceNotFound(LookupError):
    pass


class PeriodCloseBlocked(RuntimeError):
    """The close was attempted while blockers remain. Nothing was changed."""

    def __init__(self, blockers: tuple["Blocker", ...]) -> None:
        super().__init__(f"{len(blockers)} blocker(s)")
        self.blockers = blockers


class PeriodCloseConflict(RuntimeError):
    """The period is not open: already closed, or another close is in flight."""

    def __init__(self, status: str) -> None:
        super().__init__(status)
        self.status = status


class DocumentChecksumMismatch(RuntimeError):
    """A re-render produced different bytes than the recorded document.

    Two downloads of one invoice must be provably identical; a mismatch means
    a rendering defect, never a business situation, so it surfaces loudly.
    """

    def __init__(self, expected: str, actual: str) -> None:
        super().__init__(f"expected {expected}, rendered {actual}")
        self.expected = expected
        self.actual = actual


class FindingNotFound(LookupError):
    """The finding does not exist in this period, or in this organization."""


class FindingAlreadyDecided(RuntimeError):
    """A finding carries one decision; a second would overwrite the first."""
