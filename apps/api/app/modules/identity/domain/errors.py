class InvalidAccessToken(Exception):
    """The bearer token could not be cryptographically verified."""


class OrganizationAccessDenied(Exception):
    """The verified user has no organization membership."""
