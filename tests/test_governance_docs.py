"""Governance documentation, navigation hub, and playbook consistency tests."""

from __future__ import annotations

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
    """Verify BUILD_PROMPTS.md contains BUILD-PROMPT-01..10 with bootstrap headers."""
    text = (REPO_ROOT / "BUILD_PROMPTS.md").read_text(encoding="utf-8")
    for idx in range(1, 11):
        prompt_id = f"BUILD-PROMPT-{idx:02d}"
        assert prompt_id in text, f"Missing {prompt_id} in BUILD_PROMPTS.md"
    assert "Auto-Commit & Fail-Closed Verification Gate" in text
    assert "GATE FAILURE" in text


def test_legacy_plan_md_removed_and_no_stale_links() -> None:
    """Verify legacy PLAN.md is removed and no active governance docs reference it."""
    assert not (REPO_ROOT / "PLAN.md").exists(), "Legacy PLAN.md must be removed after consolidation"
    for doc_name in ["README.md", "PROJECT_MAP.md", "GEMINI.md", "BUILD_PROMPTS.md"]:
        content = (REPO_ROOT / doc_name).read_text(encoding="utf-8")
        assert "PLAN.md" not in content, f"Stale PLAN.md reference found in {doc_name}"
