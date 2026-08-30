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
