import pytest

from walk.common import errors


@pytest.mark.parametrize(
    ("cls", "parent"),
    [
        (errors.TransientError, errors.WalkError),
        (errors.ProviderUnavailable, errors.TransientError),
        (errors.RateLimited, errors.TransientError),
        (errors.Timeout, errors.TransientError),
        (errors.QuotaExhausted, errors.TransientError),
        (errors.ToolCrashed, errors.TransientError),
        (errors.PermanentError, errors.WalkError),
        (errors.PermissionDenied, errors.PermanentError),
        (errors.GuardRejected, errors.PermanentError),
        (errors.OutputInvalid, errors.PermanentError),
        (errors.BoundaryViolation, errors.PermanentError),
        (errors.ConfigError, errors.PermanentError),
        (errors.RecoverableInterruption, errors.WalkError),
    ],
)
def test_error_hierarchy_matches_taxonomy(cls: type[Exception], parent: type[Exception]) -> None:
    assert issubclass(cls, parent)
    assert cls.__doc__


def test_walk_error_detail_defaults_to_empty_dict() -> None:
    err = errors.ConfigError("bad config")
    assert err.detail == {}
    assert err.message == "bad config"
    assert str(err) == "bad config"


def test_walk_error_detail_is_copied() -> None:
    detail = {"path": "x"}
    err = errors.ToolCrashed("boom", detail=detail)
    detail["path"] = "y"
    assert err.detail == {"path": "x"}
