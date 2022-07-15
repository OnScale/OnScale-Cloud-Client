import os
import re


DEV_TOKEN_PATTERN = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{12}_[0-9]{13}_[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def is_dev_token(token: str) -> bool:
    """Check if a token string is a valid developer token."""
    return bool(DEV_TOKEN_PATTERN.match(token))


SUPERVISOR_TOKEN_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}_"
    r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)


def is_supervisor_token(token: str) -> bool:
    """Check if a token string is a valid supervisor token."""
    return bool(SUPERVISOR_TOKEN_PATTERN.match(token))


UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)


def is_uuid(token: str) -> bool:
    """Check if a token string is a valid supervisor token."""
    return bool(UUID_PATTERN.match(token))


OS_DEFAULT_PROFILE = os.getenv("ONSCALE_DEFAULT_PROFILE")
