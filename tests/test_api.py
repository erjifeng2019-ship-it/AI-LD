from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

from ai_chain_radar.api.app import app
from ai_chain_radar.briefing.renderer import render_daily_briefing
from ai_chain_radar.db.repository import Repository
from ai_chain_radar.scoring.opportunity_score import OpportunityScore
from ai_chain_radar.taxonomy.mapping import load_taxonomy

api_module = sys.modules["ai_chain_radar.api.app"]


def _seed_minimum(repo: Repository) -> None:
    repo.init_db()
    load_taxonomy(repo)
    repo.query_dataframe(
        """
        INSERT INTO global_anchor_price_daily (
          trade_date, symbol, market, close, pct_chg, source, ingested_at
        ) VALUES
          ('2026-05-28', 'MU', 'US', 120, 2.5, 'test', now())
        """
    )
    OpportunityScore().run(repo, "2026-05-28")
    render_daily_briefing(repo, "2026-05-28")


def test_api_health():
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_api_ui_index():
    client = TestClient(app)
    resp = client.get("/ui")
    assert resp.status_code == 200
    assert "AI Chain Radar Dashboard" in resp.text
    assert "Source Status" in resp.text
    assert "Credential Availability" in resp.text
    assert "Data Freshness" in resp.text
    assert "CI First Run" in resp.text
    assert "Review Summary" in resp.text
    assert "Review Trend (P/R)" in resp.text


def test_api_ui_includes_ci_note() -> None:
    ci_path = Path("docs/CI_FIRST_RUN.md")
    backup = ci_path.read_text(encoding="utf-8") if ci_path.exists() else None
    try:
        ci_path.parent.mkdir(parents=True, exist_ok=True)
        ci_path.write_text(
            "\n".join(
                [
                    "# CI_FIRST_RUN",
                    "",
                    "status: PENDING",
                    "",
                    "## Notes",
                    "- GitHub auth unavailable: gh not logged in.",
                    "",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        client = TestClient(app)
        resp = client.get("/ui")
        assert resp.status_code == 200
        assert "GitHub auth unavailable: gh not logged in." in resp.text
    finally:
        if backup is None:
            if ci_path.exists():
                ci_path.unlink()
        else:
            ci_path.write_text(backup, encoding="utf-8")


def test_api_read_endpoints():
    repo = Repository()
    _seed_minimum(repo)
    repo.close()
    client = TestClient(app)

    assert client.get("/segments").status_code == 200
    assert client.get("/anchors").status_code == 200

    latest_scores = client.get("/scores/latest")
    assert latest_scores.status_code == 200
    assert isinstance(latest_scores.json(), list)
    assert len(latest_scores.json()) >= 1

    by_date_scores = client.get("/scores/2026-05-28")
    assert by_date_scores.status_code == 200
    assert len(by_date_scores.json()) >= 1

    latest_brief = client.get("/briefings/latest")
    assert latest_brief.status_code == 200

    by_date_brief = client.get("/briefings/2026-05-28")
    assert by_date_brief.status_code == 200

    symbol_mapping = client.get("/symbols/300308.SZ/mapping")
    assert symbol_mapping.status_code == 200
    assert isinstance(symbol_mapping.json(), list)

    latest_events = client.get("/events/latest")
    assert latest_events.status_code == 200
    assert isinstance(latest_events.json(), list)

    latest_evidence = client.get("/evidence/latest")
    assert latest_evidence.status_code == 200
    assert isinstance(latest_evidence.json(), list)

    review = client.get("/review/2026-05-28")
    assert review.status_code == 200
    assert isinstance(review.json(), list)

    review_summary = client.get("/review-summary/2026-05-28")
    assert review_summary.status_code == 200
    assert isinstance(review_summary.json(), list)


def test_api_repo_ctx_uses_read_only_connection(monkeypatch):
    repo = Repository()
    repo.init_db()
    load_taxonomy(repo)
    repo.close()
    calls: list[bool] = []
    real_get_connection = api_module.get_connection

    def _spy_get_connection(*args, **kwargs):
        calls.append(bool(kwargs.get("read_only", False)))
        return real_get_connection(*args, **kwargs)

    monkeypatch.setattr(api_module, "get_connection", _spy_get_connection)
    client = TestClient(app)
    resp = client.get("/segments")
    assert resp.status_code == 200
    assert calls
    assert all(calls)
