from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

from ai_chain_radar.db.duckdb import get_connection
from ai_chain_radar.db.repository import Repository
from ai_chain_radar.settings import get_settings

app = FastAPI(title="AI Chain Radar API", version="0.1.0")
static_dir = Path(__file__).with_name("static")
ci_first_run_doc = Path("docs") / "CI_FIRST_RUN.md"


@contextmanager
def _repo_ctx() -> Iterator[Repository]:
    repo = Repository(get_connection(read_only=True))
    try:
        yield repo
    finally:
        repo.close()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/segments")
def segments() -> list[dict]:
    with _repo_ctx() as repo:
        df = repo.query_dataframe("SELECT * FROM ai_chain_segment ORDER BY segment_id")
    return df.to_dict(orient="records")


@app.get("/anchors")
def anchors() -> list[dict]:
    with _repo_ctx() as repo:
        df = repo.query_dataframe("SELECT * FROM global_anchor_security ORDER BY symbol")
    return df.to_dict(orient="records")


@app.get("/scores/latest")
def scores_latest() -> list[dict]:
    with _repo_ctx() as repo:
        df = repo.query_dataframe(
            """
            SELECT *
            FROM theme_opportunity_score
            WHERE score_date = (SELECT max(score_date) FROM theme_opportunity_score)
            ORDER BY final_score DESC
            """
        )
    return df.to_dict(orient="records")


@app.get("/scores/{score_date}")
def scores_by_date(score_date: str) -> list[dict]:
    with _repo_ctx() as repo:
        df = repo.query_dataframe(
            "SELECT * FROM theme_opportunity_score WHERE score_date = ? ORDER BY final_score DESC",
            [score_date],
        )
    return df.to_dict(orient="records")


@app.get("/briefings/latest")
def briefing_latest() -> dict:
    with _repo_ctx() as repo:
        df = repo.query_dataframe(
            """
            SELECT *
            FROM daily_ai_chain_briefing
            WHERE briefing_date = (SELECT max(briefing_date) FROM daily_ai_chain_briefing)
            """
        )
    if df.empty:
        raise HTTPException(status_code=404, detail="No briefing found")
    return df.iloc[0].to_dict()


@app.get("/briefings/{briefing_date}")
def briefing_by_date(briefing_date: str) -> dict:
    with _repo_ctx() as repo:
        df = repo.query_dataframe(
            "SELECT * FROM daily_ai_chain_briefing WHERE briefing_date = ?",
            [briefing_date],
        )
    if df.empty:
        raise HTTPException(status_code=404, detail="Briefing not found")
    return df.iloc[0].to_dict()


@app.get("/symbols/{symbol}/mapping")
def symbol_mapping(symbol: str) -> list[dict]:
    with _repo_ctx() as repo:
        df = repo.query_dataframe("SELECT * FROM a_share_chain_mapping WHERE ts_code = ?", [symbol])
    return df.to_dict(orient="records")


@app.get("/events/latest")
def events_latest(limit: int = 50) -> list[dict]:
    safe_limit = max(1, min(limit, 200))
    with _repo_ctx() as repo:
        df = repo.query_dataframe(
            """
            SELECT *
            FROM (
              SELECT
                'sec' AS source,
                filing_date AS event_date,
                symbol,
                company_name AS entity_name,
                form_type AS event_type,
                accession_number AS event_id,
                filing_url AS event_url
              FROM us_sec_filing_event
              UNION ALL
              SELECT
                'opendart' AS source,
                rcept_dt AS event_date,
                stock_code AS symbol,
                corp_name AS entity_name,
                report_nm AS event_type,
                rcept_no AS event_id,
                raw_url AS event_url
              FROM korea_disclosure_event
              UNION ALL
              SELECT
                'a_share_announcement' AS source,
                ann_date AS event_date,
                ts_code AS symbol,
                name AS entity_name,
                title AS event_type,
                ann_id AS event_id,
                url AS event_url
              FROM a_share_announcement_event
              UNION ALL
              SELECT
                'a_share_research_report' AS source,
                report_date AS event_date,
                ts_code AS symbol,
                name AS entity_name,
                report_title AS event_type,
                rating_id AS event_id,
                NULL AS event_url
              FROM a_share_report_rating_event
            ) t
            ORDER BY event_date DESC NULLS LAST, source, event_id
            LIMIT ?
            """,
            [safe_limit],
        )
    return df.to_dict(orient="records")


@app.get("/evidence/latest")
def evidence_latest(limit: int = 50, segment: str | None = None) -> list[dict]:
    safe_limit = max(1, min(limit, 200))
    with _repo_ctx() as repo:
        if segment:
            df = repo.query_dataframe(
                """
                SELECT *
                FROM evidence_registry
                WHERE segment = ?
                ORDER BY evidence_date DESC NULLS LAST, ingested_at DESC
                LIMIT ?
                """,
                [segment, safe_limit],
            )
        else:
            df = repo.query_dataframe(
                """
                SELECT *
                FROM evidence_registry
                ORDER BY evidence_date DESC NULLS LAST, ingested_at DESC
                LIMIT ?
                """,
                [safe_limit],
            )
    return df.to_dict(orient="records")


@app.get("/review/{review_date}")
def review_by_date(review_date: str, limit: int = 200) -> list[dict]:
    safe_limit = max(1, min(limit, 500))
    with _repo_ctx() as repo:
        df = repo.query_dataframe(
            """
            SELECT *
            FROM signal_review_result
            WHERE review_date = ?
            ORDER BY original_score DESC
            LIMIT ?
            """,
            [review_date, safe_limit],
        )
    return df.to_dict(orient="records")


@app.get("/review-summary/{review_date}")
def review_summary_by_date(review_date: str, limit: int = 200) -> list[dict]:
    safe_limit = max(1, min(limit, 500))
    with _repo_ctx() as repo:
        df = repo.query_dataframe(
            """
            SELECT *
            FROM signal_review_summary
            WHERE review_date = ?
            ORDER BY precision DESC, recall DESC
            LIMIT ?
            """,
            [review_date, safe_limit],
        )
    return df.to_dict(orient="records")


def _build_ui_payload() -> dict:
    latest_per_source = []
    review_summary_rows = []
    latest_review_date = ""
    latest_run_time = ""
    review_trend_dates: list[str] = []
    review_trend_series: list[dict] = []
    try:
        with _repo_ctx() as repo:
            df = repo.query_dataframe(
                """
                SELECT source, status, rows_read, rows_written, started_at
                FROM (
                  SELECT
                    source, status, rows_read, rows_written, started_at,
                    row_number() OVER (PARTITION BY source ORDER BY started_at DESC) AS rn
                  FROM source_run_log
                ) t
                WHERE rn = 1
                ORDER BY source
                """
            )
            latest_per_source = df.to_dict(orient="records")

            run_time_df = repo.query_dataframe(
                "SELECT max(started_at) AS latest_run_time FROM source_run_log"
            )
            if not run_time_df.empty and run_time_df.iloc[0]["latest_run_time"] is not None:
                latest_run_time = str(run_time_df.iloc[0]["latest_run_time"])

            latest_review_df = repo.query_dataframe(
                "SELECT max(review_date) AS review_date FROM signal_review_summary"
            )
            if not latest_review_df.empty and latest_review_df.iloc[0]["review_date"] is not None:
                latest_review_date = str(latest_review_df.iloc[0]["review_date"])
                summary_df = repo.query_dataframe(
                    """
                    SELECT
                      segment,
                      sample_count,
                      precision,
                      recall,
                      avg_forward_return_3d,
                      avg_forward_return_10d
                    FROM signal_review_summary
                    WHERE review_date = ?
                    ORDER BY precision DESC, recall DESC, sample_count DESC
                    LIMIT 10
                    """,
                    [latest_review_date],
                )
                review_summary_rows = summary_df.to_dict(orient="records")

            trend_df = repo.query_dataframe(
                """
                WITH recent_dates AS (
                  SELECT DISTINCT review_date
                  FROM signal_review_summary
                  ORDER BY review_date DESC
                  LIMIT 8
                ),
                top_segments AS (
                  SELECT segment
                  FROM signal_review_summary
                  WHERE review_date = (SELECT max(review_date) FROM signal_review_summary)
                  ORDER BY precision DESC, recall DESC, sample_count DESC
                  LIMIT 5
                )
                SELECT
                  cast(s.review_date AS TEXT) AS review_date,
                  s.segment,
                  s.precision,
                  s.recall
                FROM signal_review_summary s
                WHERE s.review_date IN (SELECT review_date FROM recent_dates)
                  AND s.segment IN (SELECT segment FROM top_segments)
                ORDER BY s.review_date ASC, s.segment ASC
                """
            )
        if not trend_df.empty:
            review_trend_dates = sorted(
                [str(v) for v in trend_df["review_date"].dropna().unique().tolist()]
            )
            segment_map: dict[str, dict[str, list[float | None]]] = {}
            for item in trend_df.itertuples(index=False):
                segment = str(item.segment)
                date_key = str(item.review_date)
                if segment not in segment_map:
                    segment_map[segment] = {
                        "precision": [None] * len(review_trend_dates),
                        "recall": [None] * len(review_trend_dates),
                    }
                idx = review_trend_dates.index(date_key)
                segment_map[segment]["precision"][idx] = (
                    float(item.precision) if item.precision is not None else None
                )
                segment_map[segment]["recall"][idx] = (
                    float(item.recall) if item.recall is not None else None
                )
            review_trend_series = [
                {
                    "segment": segment,
                    "precision": values["precision"],
                    "recall": values["recall"],
                }
                for segment, values in segment_map.items()
            ]
    except Exception:
        latest_per_source = []
        review_summary_rows = []
        latest_review_date = ""
        latest_run_time = ""
        review_trend_dates = []
        review_trend_series = []
    settings = get_settings()
    credential_availability = {
        "tushare": bool(settings.tushare_token.strip()),
        "finmind": bool(settings.finmind_token.strip()),
        "sec": bool(settings.sec_user_agent.strip()),
        "opendart": bool(settings.opendart_api_key.strip()),
    }
    source_credential_key = {
        "tushare": "tushare",
        "finmind": "finmind",
        "sec": "sec",
        "opendart": "opendart",
    }
    source_status_explained = []
    for row in latest_per_source:
        source = str(row.get("source", ""))
        status = str(row.get("status", ""))
        cred_key = source_credential_key.get(source)
        has_cred = bool(credential_availability[cred_key]) if cred_key else True
        reason = "ok"
        if status == "missing_credentials":
            reason = "degraded: credential missing"
        elif status == "failed" and has_cred:
            reason = "failed: credential available, check runtime/API"
        elif status == "failed" and not has_cred:
            reason = "failed: credential missing or invalid"
        elif status == "empty":
            reason = "empty: no rows for current window"
        source_status_explained.append(
            {
                **row,
                "credential_key": cred_key or "",
                "has_credential": has_cred,
                "reason": reason,
            }
        )
    source_counts = {
        "ok": len([item for item in latest_per_source if str(item.get("status", "")) == "ok"]),
        "missing_credentials": len(
            [
                item
                for item in latest_per_source
                if str(item.get("status", "")) == "missing_credentials"
            ]
        ),
        "failed": len(
            [item for item in latest_per_source if str(item.get("status", "")) == "failed"]
        ),
    }
    ci_first_run = {
        "status": "MISSING",
        "repo": "",
        "target_date": "",
        "acceptance_date": "",
        "run_id": "",
        "workflow_url": "",
        "conclusion": "",
        "note": "",
    }
    if ci_first_run_doc.exists():
        lines = ci_first_run_doc.read_text(encoding="utf-8").splitlines()
        in_notes = False
        notes: list[str] = []
        for raw_line in lines:
            line = raw_line.strip()
            if line == "## Notes":
                in_notes = True
                continue
            if line.startswith("## ") and line != "## Notes":
                in_notes = False
            if in_notes and line.startswith("- "):
                note = line[2:].strip()
                if note:
                    notes.append(note)
            if not line.startswith("-") and line.lower().startswith("status:"):
                ci_first_run["status"] = line.split(":", 1)[1].strip().upper()
                continue
            for key in (
                "repo",
                "target_date",
                "acceptance_date",
                "run_id",
                "workflow_url",
                "conclusion",
            ):
                prefix = f"- {key}:"
                if line.lower().startswith(prefix):
                    ci_first_run[key] = line.split(":", 1)[1].strip()
                    break
        if notes:
            ci_first_run["note"] = " | ".join(notes)
    status = ci_first_run.get("status", "MISSING")
    run_id_present = bool(ci_first_run.get("run_id"))
    workflow_present = bool(ci_first_run.get("workflow_url"))
    if status == "PASS" and run_id_present and workflow_present:
        ci_reason = "pass: workflow evidence recorded"
    elif status == "PASS":
        ci_reason = "incomplete: PASS without run_id/workflow_url"
    elif status == "PENDING":
        ci_reason = "pending: waiting for workflow_dispatch run"
    elif status == "FAIL":
        ci_reason = "failed: check workflow_url/conclusion"
    else:
        ci_reason = "missing: no CI first run record"
    ci_first_run["reason"] = ci_reason

    return {
        "source_status": source_status_explained,
        "credential_availability": credential_availability,
        "review_summary_rows": review_summary_rows,
        "review_trend_dates": review_trend_dates,
        "review_trend_series": review_trend_series,
        "latest_review_date": latest_review_date,
        "latest_run_time": latest_run_time,
        "source_counts": source_counts,
        "ci_first_run": ci_first_run,
    }


@app.get("/ui", response_class=HTMLResponse)
def ui_dashboard() -> HTMLResponse:
    html = (static_dir / "index.html").read_text(encoding="utf-8")
    payload = json.dumps(_build_ui_payload(), ensure_ascii=False, default=str)
    return HTMLResponse(html.replace("__UI_PAYLOAD__", payload))
