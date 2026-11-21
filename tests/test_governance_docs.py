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
