import re
import time

import pytest
from pydantic import TypeAdapter, ValidationError

from walk.common.ids import ULID_PATTERN, FeatureId, format_seq_id, new_ulid, parse_prefix


def test_new_ulid_is_26_chars_and_time_ordered() -> None:
    first = new_ulid()
    time.sleep(0.002)
    second = new_ulid()
    assert re.fullmatch(ULID_PATTERN, first)
    assert re.fullmatch(ULID_PATTERN, second)
    assert second > first


def test_format_seq_id_zero_pads() -> None:
    assert format_seq_id("FEAT", 12, 4) == "FEAT-0012"
    assert format_seq_id("EVD", 1234567, 6) == "EVD-1234567"


def test_format_seq_id_rejects_non_positive() -> None:
    with pytest.raises(ValueError, match="must be >= 1"):
        format_seq_id("X", 0, 4)


def test_parse_prefix_handles_compound_prefix_and_rejects_garbage() -> None:
    assert parse_prefix("OBS-K-0001") == "OBS-K"
    assert parse_prefix("FEAT-0012") == "FEAT"
    with pytest.raises(ValueError, match="not a sequence id"):
        parse_prefix("nodash")


def test_feature_id_pattern_enforces_min_width() -> None:
    adapter: TypeAdapter[str] = TypeAdapter(FeatureId)
    assert adapter.validate_python("FEAT-0012") == "FEAT-0012"
    assert adapter.validate_python("FEAT-12345") == "FEAT-12345"
    with pytest.raises(ValidationError):
        adapter.validate_python("FEAT-12")
