class InvalidJustification(ValueError):
    def __init__(self, field: str) -> None:
        super().__init__(field)
        self.field = field


class SessionNotFound(LookupError):
    pass


class UnitNotFound(LookupError):
    pass


class AssignmentForbidden(PermissionError):
    pass


class InvalidPeriod(ValueError):
    pass


class CardAlreadyRegistered(ValueError):
    """A card answers for exactly one unit; two would make a charge ambiguous."""


class CardNotFound(LookupError):
    pass


class CardIsTheChargerSerial(ValueError):
    """The equipment's own serial is not a person's card.

    Registering it would make every charge on the connector belong to one unit
    by construction, and the invoice would state an identity nobody verified.
    """
