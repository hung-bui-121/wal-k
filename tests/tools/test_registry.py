from pathlib import Path

import pytest

from walk.common.errors import ConfigError
from walk.tools import DefaultToolRegistry, ToolKind, ToolRegistry, ToolSpec, load_tool_specs


def _yaml(tmp_path: Path, text: str, name: str = "tools.yaml") -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture
def registry() -> DefaultToolRegistry:
    return DefaultToolRegistry(load_tool_specs([]))


def _names(specs: list[ToolSpec]) -> set[str]:
    return {spec.name for spec in specs}


def test_default_registry_satisfies_protocol(registry: DefaultToolRegistry) -> None:
    protocol: ToolRegistry = registry
    assert protocol is registry


def test_project_override_replaces_builtin(tmp_path: Path) -> None:
    project = _yaml(
        tmp_path,
        "tools:\n"
        "  - name: bash\n"
        "    kind: PROVIDER_NATIVE\n"
        "    description: Project shell\n"
        "    requires_env: [git]\n"
        "  - name: blender.render\n"
        "    kind: KERNEL\n"
        "    description: Render\n"
        "    provider: blender\n",
    )
    specs = load_tool_specs([project])
    by_name = {spec.name: spec for spec in specs}
    assert by_name["bash"].description == "Project shell"
    assert by_name["bash"].requires_env == ["git"]
    assert [spec.name for spec in specs].count("bash") == 1
    assert specs[-1].name == "blender.render"


def test_duplicate_tool_name_rejected(tmp_path: Path) -> None:
    project = _yaml(
        tmp_path,
        "tools:\n"
        "  - {name: lint, kind: KERNEL, description: a}\n"
        "  - {name: lint, kind: KERNEL, description: b}\n",
    )
    with pytest.raises(ConfigError, match="duplicate tool 'lint'"):
        load_tool_specs([project])


def test_invalid_row_names_its_index(tmp_path: Path) -> None:
    project = _yaml(
        tmp_path,
        "tools:\n"
        "  - {name: lint, kind: KERNEL, description: a}\n"
        "  - {name: Bad Name, kind: KERNEL, description: b}\n",
    )
    with pytest.raises(ConfigError, match="row 2") as info:
        load_tool_specs([project])
    assert info.value.detail["row"] == 2


@pytest.mark.parametrize(
    "text",
    [
        "tools: [\n",
        "tools: not-a-list\n",
        "other: []\n",
        "tools:\n  - {name: x, kind: CLI, description: d, command_patterns: ['^x']}\n",
        (
            "tools:\n  - {name: x, kind: CLI, description: d, executable: x,"
            " command_patterns: ['(']}\n"
        ),
    ],
)
def test_malformed_tool_files_rejected(tmp_path: Path, text: str) -> None:
    with pytest.raises(ConfigError, match=r"tools\.yaml"):
        load_tool_specs([_yaml(tmp_path, text)])


def test_missing_tool_file_rejected(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match=r"missing\.yaml"):
        load_tool_specs([tmp_path / "missing.yaml"])


def test_registry_rejects_duplicate_specs() -> None:
    spec = ToolSpec(name="bash", kind=ToolKind.PROVIDER_NATIVE, description="shell")
    with pytest.raises(ConfigError, match="duplicate tool 'bash'"):
        DefaultToolRegistry([spec, spec])


def test_available_filters_by_env(registry: DefaultToolRegistry) -> None:
    available = _names(registry.available({"git"}))
    assert "unity.compile" not in available
    assert "unity-cli" not in available
    assert "graph.query" not in available
    assert "asset.generate" not in available
    assert {"bash", "git.commit", "git-cli"} <= available


def test_available_accepts_any_alternative(registry: DefaultToolRegistry) -> None:
    assert "asset.generate" in _names(registry.available({"openart"}))
    assert "asset.generate" in _names(registry.available({"meshy"}))


def test_for_role_missing_required_raises(registry: DefaultToolRegistry) -> None:
    with pytest.raises(ConfigError, match=r"unity\.compile") as info:
        registry.for_role(["bash"], {"git"}, ["unity.compile"])
    assert info.value.detail["missing"] == ["unity.compile"]
    with pytest.raises(ConfigError, match="nope"):
        registry.for_role([], {"git"}, ["nope"])


def test_for_role_returns_allowed_and_required_available(registry: DefaultToolRegistry) -> None:
    specs = registry.for_role(
        ["bash", "unity.build", "unknown.tool"], {"git", "unity"}, ["git.commit"]
    )
    assert [spec.name for spec in specs] == ["bash", "git.commit", "unity.build"]
    assert _names(registry.for_role(["unity.build"], {"git"}, [])) == set()


def test_identify_matches_cli_patterns(registry: DefaultToolRegistry) -> None:
    spec = registry.identify("git status --porcelain")
    assert spec is not None
    assert spec.name == "git-cli"
    assert registry.identify("ls") is None
    assert registry.identify("gitk") is None
    unity = registry.identify("Unity.exe -batchmode -quit")
    assert unity is not None
    assert unity.name == "unity-cli"
    graphify = registry.identify("  graphify query Player")
    assert graphify is not None
    assert graphify.name == "graphify-cli"


def test_get_unknown_raises(registry: DefaultToolRegistry) -> None:
    assert registry.get("git.commit").provider == "git"
    with pytest.raises(ConfigError, match="nope"):
        registry.get("nope")


def test_all_lists_the_catalogue_in_load_order(registry: DefaultToolRegistry) -> None:
    names = [spec.name for spec in registry.all()]
    assert names[0] == "bash"
    assert names == [spec.name for spec in load_tool_specs([])]
