"""Secret-pattern scan applied to every `.ai/` write (ARCHITECTURE §6, §91)."""

import re
from typing import Final

_NAMED_PATTERNS: Final = {
    "aws_access_key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "openai_key": re.compile(r"\bsk-[A-Za-z0-9]{20,}"),
    "github_token": re.compile(r"\bghp_[A-Za-z0-9]{36}"),
    "atlassian_token": re.compile(r"\bATATT[A-Za-z0-9_-]{20,}"),
    "private_key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
}

SECRET_PATTERNS: tuple[re.Pattern[str], ...] = tuple(_NAMED_PATTERNS.values())
"""Patterns whose match makes `MemoryManager` refuse a write."""


def find_secrets(text: str) -> list[str]:
    """Names of the secret patterns found in ``text``, in pattern order; ``[]`` when clean."""
    return [name for name, pattern in _NAMED_PATTERNS.items() if pattern.search(text)]
