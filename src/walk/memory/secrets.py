"""The one secret scanner: `.ai/` writes and agent diffs (ARCHITECTURE §6, §91; E02-S14).

`MemoryManager.write` refuses documents that match a pattern; `BoundaryAuditor` gets
`contains_secret` injected by the composition root (``runtime`` may not import this module).
"""

import re
from typing import Final

SECRET_PATTERNS: tuple[tuple[str, str], ...] = (
    ("anthropic_key", r"\bsk-ant-[A-Za-z0-9_-]{20,}"),
    ("openai_key", r"\bsk-[A-Za-z0-9]{32,}"),
    ("aws_access_key", r"\bAKIA[0-9A-Z]{16}"),
    ("github_token", r"\bgh[pousr]_[A-Za-z0-9]{36,}"),
    ("jira_token", r"\bATATT3[A-Za-z0-9_-]{20,}"),
    ("private_key", r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    (
        "generic_assignment",
        r"(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*['\"][^'\"\s]{12,}['\"]",
    ),
)
"""``(name, regex)`` pairs, checked in order; a match makes a write or a diff a violation."""

_COMPILED: Final = tuple((name, re.compile(regex)) for name, regex in SECRET_PATTERNS)


def contains_secret(text: str) -> str | None:
    """The name of the first secret pattern found in ``text``; None when clean."""
    return next((name for name, pattern in _COMPILED if pattern.search(text)), None)


def find_secrets(text: str) -> list[str]:
    """Names of every secret pattern found in ``text``, in pattern order; ``[]`` when clean."""
    return [name for name, pattern in _COMPILED if pattern.search(text)]
