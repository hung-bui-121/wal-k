from walk.budgets import BudgetDimension, CostCategory
from walk.tools import ToolKind, load_tool_specs

PROVIDER_NATIVE = ["bash", "read", "write", "edit", "glob", "grep"]
KERNEL = {
    "git": ["git.commit", "git.push", "git.merge_protected", "git.delete_branch_protected"],
    "jira": [
        "jira.create_task",
        "jira.create_bug",
        "jira.transition",
        "jira.comment",
        "jira.close_feature",
        "jira.reopen",
        "jira.delete",
    ],
    "kernel": [
        "review.approve",
        "review.reject",
        "qc.approve",
        "qc.reject",
        "work.plan",
        "permissions.alter",
        "credentials.change",
        "monetization.change",
        "repo.delete_data",
        "store.publish",
    ],
    "unity": ["unity.compile", "unity.run_tests", "unity.build"],
    "graphify": ["graph.query", "graph.neighbors"],
    "asset": ["asset.generate"],
}
CLI = {"git-cli": "git", "dotnet": "dotnet", "graphify-cli": "graphify", "unity-cli": "Unity"}
PROTECTED = {
    "git.merge_protected",
    "git.delete_branch_protected",
    "jira.delete",
    "permissions.alter",
    "credentials.change",
    "monetization.change",
    "repo.delete_data",
    "store.publish",
}
REQUIRES_ENV = {
    "unity.compile": ["unity"],
    "unity.run_tests": ["unity"],
    "unity.build": ["unity"],
    "graph.query": ["graphify"],
    "graph.neighbors": ["graphify"],
    "asset.generate": ["meshy|openart"],
}


def test_builtin_tools_cover_mvp_list() -> None:
    specs = {spec.name: spec for spec in load_tool_specs([])}
    expected_kernel = [name for names in KERNEL.values() for name in names]
    assert set(specs) == {*PROVIDER_NATIVE, *expected_kernel, *CLI}
    assert all(specs[name].kind is ToolKind.PROVIDER_NATIVE for name in PROVIDER_NATIVE)
    for provider, names in KERNEL.items():
        for name in names:
            assert (specs[name].kind, specs[name].provider) == (ToolKind.KERNEL, provider), name
            assert specs[name].requires_env == REQUIRES_ENV.get(name, []), name
    for name, executable in CLI.items():
        assert (specs[name].kind, specs[name].executable) == (ToolKind.CLI, executable)
        assert specs[name].command_patterns, name
    assert all(spec.description for spec in specs.values())
    assert all(spec.cost_dimension is BudgetDimension.TOOL_CALLS for spec in specs.values())
    assert all(spec.cost_category is CostCategory.COMPUTE for spec in specs.values())


def test_protected_tools_declare_protected_action() -> None:
    specs = load_tool_specs([])
    protected = {spec.name for spec in specs if spec.protected_action is not None}
    assert protected == PROTECTED
    assert all(spec.protected_action == spec.name for spec in specs if spec.name in PROTECTED)
