"""Governance documentation, navigation hub, and playbook consistency tests."""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_governance_files_exist() -> None:
    """Verify required Tier-1 governance and playbook artifacts exist with exact casing."""
    required_files = [
        "GEMINI.md",
        "Enterprise_Blueprint.md",
        "AUDIT_REMEDIATION_LOG.md",
        "PROJECT_MAP.md",
        "BUILD_PROMPTS.md",
        "README.md",
    ]
    for rel_path in required_files:
        target = REPO_ROOT / rel_path
        assert target.is_file(), f"Missing required governance artifact: {rel_path}"

    # Verify case-sensitive filename in directory listing (important for Linux/Docker)
    root_names = {p.name for p in REPO_ROOT.iterdir()}
    assert "GEMINI.md" in root_names
    assert "gemini.md" not in root_names


def test_readme_master_navigation_hub_has_zero_broken_links() -> None:
    """Verify README.md links all governance/spec docs with zero broken relative Markdown links."""
    readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

    # Verify key governance documents are linked in README.md
    for doc in [
        "GEMINI.md",
        "Enterprise_Blueprint.md",
        "AUDIT_REMEDIATION_LOG.md",
        "PROJECT_MAP.md",
        "BUILD_PROMPTS.md",
    ]:
        assert doc in readme_text, f"README.md Master Navigation Hub missing link to {doc}"

    # Extract all relative Markdown links [text](target) excluding http(s) and #anchors
    link_pattern = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
    for raw_target in link_pattern.findall(readme_text):
        target = raw_target.strip()
        if target.startswith(("http://", "https://", "#", "mailto:")):
            continue
        clean_target = target.split("#", 1)[0]
        if not clean_target:
            continue
        resolved = REPO_ROOT / clean_target
        assert resolved.exists(), f"Broken relative Markdown link in README.md: {raw_target}"


def test_build_prompts_bootstrap_and_fail_closed_gate() -> None:
    """Verify BUILD_PROMPTS.md contains BUILD-PROMPT-01..10 with 3-line bootstrap headers."""
    text = (REPO_ROOT / "BUILD_PROMPTS.md").read_text(encoding="utf-8")
    persona_line = (
        "Act as a Principal AI Security Architect and Staff Python SRE executing "
        "Tier-1 production remediation on `gemini-cost-arbiter-mcp`."
    )
    assert text.count(persona_line) == 10
    for idx in range(1, 11):
        prompt_id = f"BUILD-PROMPT-{idx:02d}"
        assert prompt_id in text, f"Missing {prompt_id} in BUILD_PROMPTS.md"
        assert f"Execute ONLY this task (`{prompt_id}`)" in text
    assert "Auto-Commit & Fail-Closed Verification Gate" in text
    assert "GATE FAILURE" in text


def test_legacy_plan_md_removed_and_no_stale_links() -> None:
    """Verify legacy PLAN.md is removed and no active governance docs reference it."""
    assert not (REPO_ROOT / "PLAN.md").exists(), "Legacy PLAN.md must be removed after consolidation"
    for doc_name in ["README.md", "PROJECT_MAP.md", "GEMINI.md", "BUILD_PROMPTS.md"]:
        content = (REPO_ROOT / doc_name).read_text(encoding="utf-8")
        assert "PLAN.md" not in content, f"Stale PLAN.md reference found in {doc_name}"


def test_deployment_docs_and_packages_valid() -> None:
    """Verify standardized docs/ and multi-cloud deploy/ packages exist and parse cleanly."""
    required_paths = [
        "docs/DEPLOYMENT_AWS.md",
        "docs/DEPLOYMENT_AZURE.md",
        "docs/DEPLOYMENT_GEMINI.md",
        "docs/Repo_Baseline_AuditReport.md",
        "deploy/aws/deploy-ec2.sh",
        "deploy/aws/docker-compose.prod.yml",
        "deploy/aws/lambda-adapter/Dockerfile",
        "deploy/azure/deploy-azure.sh",
        "deploy/azure/docker-compose.azure.yml",
        "deploy/gemini/cloudbuild.yaml",
        "deploy/gemini/service.yaml",
        "deploy/gemini/mcp_configs.example.json",
    ]
    for rel_path in required_paths:
        assert (REPO_ROOT / rel_path).is_file(), f"Missing deployment asset: {rel_path}"

    assert not (REPO_ROOT / "Repo_Baseline_AuditReport.md").exists()
    assert not (REPO_ROOT / "docs/AWS_Deployment_Guide.md").exists()

    mcp_cfg = json.loads((REPO_ROOT / "deploy/gemini/mcp_configs.example.json").read_text(encoding="utf-8"))
    assert "mcpServers" in mcp_cfg

    for yaml_rel in [
        "deploy/aws/docker-compose.prod.yml",
        "deploy/azure/docker-compose.azure.yml",
        "deploy/gemini/cloudbuild.yaml",
        "deploy/gemini/service.yaml",
    ]:
        yaml_text = (REPO_ROOT / yaml_rel).read_text(encoding="utf-8")
        assert yaml_text.strip(), f"Empty YAML manifest: {yaml_rel}"
        assert "\t" not in yaml_text, f"Tab indentation found in YAML manifest: {yaml_rel}"


async def test_mcp_resource_uris_and_prompts_registry_synced(tmp_path: Path) -> None:
    """Assert 100% MCP finops:// URI parity and prompts/modular_prompt.md registry coverage."""
    from gemini_cost_arbiter.config import ArbiterConfig
    from gemini_cost_arbiter.engine import GeminiCostArbiterEngine

    engine = GeminiCostArbiterEngine(
        config=ArbiterConfig(
            gemini_api_key="test-key",
            openrouter_api_key="mock_key",
            environment="test",
            db_path=str(tmp_path / "gov_test.db"),
        )
    )
    resp = await engine.handle_mcp_message({"jsonrpc": "2.0", "id": 1, "method": "resources/list", "params": {}})
    assert resp is not None
    resources = resp["result"]["resources"]
    uris = [str(r["uri"]) for r in resources]
    assert len(uris) >= 3
    assert all(uri.startswith("finops://") for uri in uris)

    for doc_name in [
        "GEMINI.md",
        "README.md",
        "docs/ARCHITECTURE.md",
        "docs/DEPLOYMENT_AWS.md",
        "docs/DEPLOYMENT_AZURE.md",
        "docs/DEPLOYMENT_GEMINI.md",
    ]:
        doc_text = (REPO_ROOT / doc_name).read_text(encoding="utf-8")
        for uri in uris:
            assert uri in doc_text, f"MCP resource URI {uri} missing from {doc_name}"

    modular_path = REPO_ROOT / "prompts/modular_prompt.md"
    assert modular_path.is_file(), "Missing prompts/modular_prompt.md"
    modular_text = modular_path.read_text(encoding="utf-8")
    assert "master_system_prompt.md" in modular_text
    module_files = sorted((REPO_ROOT / "prompts/modules").glob("*.md"))
    assert len(module_files) == 6
    for mod in module_files:
        assert mod.name in modular_text, f"Module {mod.name} missing from prompts/modular_prompt.md"


def test_prompt_registry_and_docs_sync_invariants() -> None:
    """Verify docs reference sample_telemetry.json, clean_gemini_schema(), and DEFAULT_MODEL."""
    for doc_name in [
        "GEMINI.md",
        "README.md",
        "prompts/README.md",
        "prompts/modular_prompt.md",
        "docs/ARCHITECTURE.md",
        "docs/DEPLOYMENT_AWS.md",
        "docs/DEPLOYMENT_AZURE.md",
        "docs/DEPLOYMENT_GEMINI.md",
    ]:
        text = (REPO_ROOT / doc_name).read_text(encoding="utf-8")
        assert "telemetry_sample.json" not in text, f"Stale telemetry_sample.json in {doc_name}"
        assert "sample_telemetry.json" in text or doc_name.startswith("prompts/"), (
            f"Missing sample_telemetry.json reference in {doc_name}"
        )
        assert "clean_gemini_schema()" in text, f"Missing clean_gemini_schema() in {doc_name}"
        assert "DEFAULT_MODEL" in text, f"Missing DEFAULT_MODEL in {doc_name}"

    arch_text = (REPO_ROOT / "docs/ARCHITECTURE.md").read_text(encoding="utf-8")
    assert "52 unit" not in arch_text
    readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert "55-test" not in readme_text
    assert "55%2F55" not in readme_text


def test_all_markdown_docs_linked_in_readme_and_zero_open_remediations() -> None:
    """Enforce the Mandatory Hyperlinked README Navigation Hub Standard and 100% DONE remediation log."""
    readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    linked_targets = {
        m.split("#", 1)[0].strip().lstrip("./")
        for m in re.findall(r"\[[^\]]+\]\(([^)]+)\)", readme_text)
        if not m.startswith(("http://", "https://", "#", "mailto:"))
    }

    expected_md_files: list[Path] = []
    for p in REPO_ROOT.glob("*.md"):
        if p.name in {"README.md"} or p.name.startswith("External_"):
            continue
        expected_md_files.append(p)
    expected_md_files.extend(sorted((REPO_ROOT / "docs").glob("*.md")))
    expected_md_files.extend(sorted((REPO_ROOT / "prompts").rglob("*.md")))

    for md_file in expected_md_files:
        rel_posix = md_file.relative_to(REPO_ROOT).as_posix()
        assert rel_posix in linked_targets, (
            f"Markdown document '{rel_posix}' is not linked via clickable [Label]({rel_posix}) in README.md"
        )

    audit_text = (REPO_ROOT / "AUDIT_REMEDIATION_LOG.md").read_text(encoding="utf-8")
    assert "18 DONE / 0 OPEN" in audit_text
    assert "0 OPEN" in audit_text
