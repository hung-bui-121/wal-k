import pytest

from walk.memory import SECRET_PATTERNS, find_secrets

# Assembled at runtime so that this file itself does not look like it holds secrets.
SAMPLES = {
    "aws_access_key": "AKIA" + "ABCDEFGHIJKLMNOP",
    "openai_key": "sk-" + "a" * 24,
    "github_token": "ghp_" + "b" * 36,
    "atlassian_token": "ATATT" + "c" * 24,
    "private_key": "-----BEGIN RSA " + "PRIVATE KEY-----",
}


def test_secret_patterns_detect_and_pass() -> None:
    assert len(SECRET_PATTERNS) == len(SAMPLES)
    for name, sample in SAMPLES.items():
        assert find_secrets(f"config: {sample}\n") == [name], name
    assert find_secrets("plain text, sk-short, AKIA123, ghp_x") == []
    everything = " ".join(SAMPLES.values())
    assert find_secrets(everything) == list(SAMPLES)


@pytest.mark.parametrize("text", ["task-1234567890123456789012", "risk-" + "d" * 30])
def test_word_boundary_avoids_false_positives(text: str) -> None:
    assert find_secrets(text) == []
