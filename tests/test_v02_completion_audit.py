from __future__ import annotations

from pathlib import Path

from ai_chain_radar.db.repository import Repository
from ai_chain_radar.reports.v02_completion_audit import export_v02_completion_audit


def _write_ci_first_run(status: str, *, include_evidence: bool = False) -> None:
    Path("docs").mkdir(parents=True, exist_ok=True)
    lines = ["# CI_FIRST_RUN", "", f"status: {status}", ""]
    if include_evidence:
        lines.extend(
            [
                "## Result",
                "- workflow_url: https://github.com/example/repo/actions/runs/123",
                "- run_id: 123",
                "",
            ]
        )
    Path("docs/CI_FIRST_RUN.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def test_v02_audit_ci_gate_pass_and_fail() -> None:
    repo = Repository()
    repo.init_db()
    ci_path = Path("docs/CI_FIRST_RUN.md")
    backup = ci_path.read_text(encoding="utf-8") if ci_path.exists() else None
    try:
        _write_ci_first_run("PASS", include_evidence=True)
        payload = export_v02_completion_audit(
            repo=repo,
            date="2026-05-28",
            reviewer="test",
            include_ci_gate=True,
        )
        ci_item = next(item for item in payload["checks"] if item["key"] == "ci_first_run")
        assert ci_item["passed"] is True

        _write_ci_first_run("PASS", include_evidence=False)
        payload_missing_evidence = export_v02_completion_audit(
            repo=repo,
            date="2026-05-28",
            reviewer="test",
            include_ci_gate=True,
        )
        ci_item_missing_evidence = next(
            item for item in payload_missing_evidence["checks"] if item["key"] == "ci_first_run"
        )
        assert ci_item_missing_evidence["passed"] is False

        _write_ci_first_run("PENDING")
        payload2 = export_v02_completion_audit(
            repo=repo,
            date="2026-05-28",
            reviewer="test",
            include_ci_gate=True,
        )
        ci_item2 = next(item for item in payload2["checks"] if item["key"] == "ci_first_run")
        assert ci_item2["passed"] is False
    finally:
        if backup is None:
            if ci_path.exists():
                ci_path.unlink()
        else:
            ci_path.write_text(backup, encoding="utf-8")


def test_v02_audit_without_ci_gate() -> None:
    repo = Repository()
    repo.init_db()
    payload = export_v02_completion_audit(
        repo=repo,
        date="2026-05-28",
        reviewer="test",
        include_ci_gate=False,
    )
    keys = {item["key"] for item in payload["checks"]}
    assert "ci_first_run" not in keys
