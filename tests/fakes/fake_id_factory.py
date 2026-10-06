"""Deterministic ID allocation for tests."""

from collections import defaultdict

from walk.common.ids import format_seq_id

# Minimum widths from DOMAIN-MODEL §2.
_WIDTHS: dict[str, int] = {
    "PHASE": 2,
    "EPIC": 3,
    "FEAT": 4,
    "STORY": 4,
    "TASK": 4,
    "BUG": 4,
    "DEC": 4,
    "DEB": 4,
    "EVD": 6,
    "APR": 4,
    "HO": 4,
    "APV": 4,
    "RC": 2,
    "OBS": 4,
    "OBS-K": 4,
    "IMP": 2,
    "PATTERN": 3,
    "ANTI": 3,
    "EXP": 4,
}
_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def _encode_ulid(n: int) -> str:
    chars = []
    for _ in range(26):
        n, rem = divmod(n, 32)
        chars.append(_CROCKFORD[rem])
    return "".join(reversed(chars))


class SequentialIdFactory:
    """Allocates FEAT-0001, FEAT-0002, ... per prefix and increasing fake ULIDs."""

    def __init__(self) -> None:
        """Start every sequence at 1."""
        self._counters: defaultdict[str, int] = defaultdict(int)
        self._ulid_counter = 0

    def next_sequence(self, prefix: str) -> str:
        """Return the next ID for ``prefix`` with the DOMAIN-MODEL §2 width."""
        self._counters[prefix] += 1
        return format_seq_id(prefix, self._counters[prefix], _WIDTHS.get(prefix, 4))

    def new_ulid(self) -> str:
        """Return a deterministic, strictly increasing ULID-shaped string."""
        self._ulid_counter += 1
        return _encode_ulid(self._ulid_counter)


__all__ = ["SequentialIdFactory"]
