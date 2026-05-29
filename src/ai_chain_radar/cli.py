from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import typer

from ai_chain_radar.briefing.renderer import render_daily_briefing
from ai_chain_radar.db.repository import Repository
from ai_chain_radar.evidence.extractor import extract_evidence_for_date
from ai_chain_radar.evidence.registry import EvidenceRegistry, ManualEvidenceInput
from ai_chain_radar.importers.global_price_importer import GlobalPriceImporter
from ai_chain_radar.importers.mapping_importer import MappingImporter
from ai_chain_radar.reports.alert_report import build_alert_report
from ai_chain_radar.reports.data_quality_report import build_data_quality_report
from ai_chain_radar.reports.missing_data_report import build_missing_data_report
from ai_chain_radar.reports.network_acceptance_report import export_network_acceptance_report
from ai_chain_radar.reports.text_cleanup import cleanup_mojibake_text
from ai_chain_radar.reports.v02_completion_audit import export_v02_completion_audit
from ai_chain_radar.reports.weekly_report import export_weekly_report
from ai_chain_radar.review.calibration import build_review_summary
from ai_chain_radar.review.calibration_report import export_scoring_calibration
from ai_chain_radar.review.signal_review import run_signal_review
from ai_chain_radar.scoring.global_anchor_score import GlobalAnchorScore
from ai_chain_radar.scoring.opportunity_score import OpportunityScore
from ai_chain_radar.scoring.trading_confirmation_score import TradingConfirmationScore
from ai_chain_radar.sources.base import SourceRequest, SyncResult
from ai_chain_radar.sources.finmind_adapter import FinMindAdapter
from ai_chain_radar.sources.global_anchor_adapter import GlobalAnchorAdapter
from ai_chain_radar.sources.opendart_adapter import OpenDartAdapter
from ai_chain_radar.sources.sec_adapter import SecAdapter
from ai_chain_radar.sources.tushare_adapter import TushareAdapter
from ai_chain_radar.taxonomy.mapping import load_taxonomy
from ai_chain_radar.taxonomy.segments import list_segments

app = typer.Typer(help="AI Chain Radar CLI")
sync_app = typer.Typer(help="Sync datasets from sources")
show_app = typer.Typer(help="Show metadata")
import_app = typer.Typer(help="Import seed/manual data")
extract_app = typer.Typer(help="Extract derived data")
evidence_app = typer.Typer(help="Manage evidence registry")
db_app = typer.Typer(help="Database helper commands")
dq_app = typer.Typer(help="Data quality commands")
calibrate_app = typer.Typer(help="Calibration commands")
export_app = typer.Typer(help="Export commands")
app.add_typer(sync_app, name="sync")
app.add_typer(show_app, name="show")
app.add_typer(import_app, name="import")
app.add_typer(extract_app, name="extract")
app.add_typer(evidence_app, name="evidence")
app.add_typer(db_app, name="db")
app.add_typer(dq_app, name="dq")
app.add_typer(calibrate_app, name="calibrate")
app.add_typer(export_app, name="export")

TUSHARE_EVENT_DATASETS = ["anns_d", "research_report", "report_rc"]
TUSHARE_REALTIME_DATASETS = [
    "daily",
    "daily_basic",
    "limit_list_d",
    "top_list",
    "top_inst",
    "moneyflow",
    "margin_detail",
]


@app.command("init-db")
def init_db() -> None:
    repo = Repository()
    repo.init_db()
    typer.echo("Database initialized.")


@app.command("load-taxonomy")
def load_taxonomy_cmd() -> None:
    repo = Repository()
    repo.init_db()
    stats = load_taxonomy(repo)
    typer.echo(f"Taxonomy loaded: {stats}")


@show_app.command("segments")
def show_segments() -> None:
    repo = Repository()
    df = list_segments(repo)
    if df.empty:
        typer.echo("No segments found. Run `ai-chain load-taxonomy` first.")
        return
    typer.echo(df.to_string(index=False))


def _run_and_log(results: list, repo: Repository) -> None:
    for item in results:
        repo.write_run_log(item)
        typer.echo(
            f"[{item.source}:{item.dataset}] status={item.status} read={item.rows_read} "
            f"written={item.rows_written}"
        )
        if item.error_message:
            typer.echo(f"  note: {item.error_message}")


def _write_operation_log(
    repo: Repository,
    source: str,
    job_name: str,
    params: dict,
    status: str,
    rows_read: int,
    rows_written: int,
    error_message: str | None = None,
) -> None:
    now = datetime.now(UTC).replace(tzinfo=None)
    repo.write_run_log(
        SyncResult(
            run_id=uuid4().hex,
            source=source,
            dataset=job_name,
            params=params,
            rows_read=rows_read,
            rows_written=rows_written,
            status=status,
            started_at=now,
            ended_at=now,
            error_message=error_message,
        )
    )


def _run_market_confirmation_only(repo: Repository, date: str, intraday: bool) -> int:
    rows = TradingConfirmationScore().run_segment_daily(
        repo=repo,
        score_date=date,
        intraday=intraday,
    )
    _write_operation_log(
        repo=repo,
        source="scoring",
        job_name="market_confirmation",
        params={"date": date, "intraday": intraday},
        status="ok" if rows > 0 else "empty",
        rows_read=rows,
        rows_written=rows,
    )
    return rows


def _run_global_anchor_score_only(repo: Repository, date: str) -> int:
    segments_df = repo.query_dataframe(
        "SELECT segment_id, segment_name FROM ai_chain_segment ORDER BY segment_id"
    )
    if segments_df.empty:
        _write_operation_log(
            repo=repo,
            source="scoring",
            job_name="global_anchor_score",
            params={"date": date},
            status="empty",
            rows_read=0,
            rows_written=0,
            error_message="ai_chain_segment is empty, run `ai-chain load-taxonomy` first",
        )
        return 0

    scorer = GlobalAnchorScore()
    rows = 0
    for row in segments_df.itertuples(index=False):
        out = scorer.score(repo=repo, segment=str(row.segment_id), score_date=date)
        typer.echo(
            f"{row.segment_id} ({row.segment_name}): "
            f"score={out.score:.2f}, confidence={out.confidence:.2f}"
        )
        rows += 1
    _write_operation_log(
        repo=repo,
        source="scoring",
        job_name="global_anchor_score",
        params={"date": date},
        status="ok" if rows > 0 else "empty",
        rows_read=rows,
        rows_written=rows,
    )
    return rows


@sync_app.command("tushare")
def sync_tushare(
    date: str = typer.Option(..., help="Trade date, e.g. 2026-05-28"),
    dry_run: bool = typer.Option(False, help="Only fetch and validate"),
    prefer_cache: bool = typer.Option(
        True, "--prefer-cache/--no-prefer-cache", help="Prefer existing raw cache before network"
    ),
    events_only: bool = typer.Option(
        False, "--events-only", help="Sync only event datasets (anns_d/research_report/report_rc)"
    ),
    realtime: bool = typer.Option(
        False,
        "--realtime",
        help="Sync only realtime-like confirmation datasets (MVP proxy mode)",
    ),
) -> None:
    if events_only and realtime:
        raise typer.BadParameter("--events-only and --realtime cannot be used together")
    repo = Repository()
    repo.init_db()
    adapter = TushareAdapter(repo)
    extra = {"prefer_raw_cache": prefer_cache}
    if events_only:
        targets = TUSHARE_EVENT_DATASETS
    elif realtime:
        targets = TUSHARE_REALTIME_DATASETS
    else:
        targets = []

    if targets:
        results = []
        for dataset in targets:
            results.extend(
                adapter.sync(
                    SourceRequest(
                        date=date,
                        dataset=dataset,
                        dry_run=dry_run,
                        extra=extra,
                    )
                )
            )
    else:
        results = adapter.sync(SourceRequest(date=date, dry_run=dry_run, extra=extra))
    _run_and_log(results, repo)


@sync_app.command("finmind")
def sync_finmind(
    start: str = typer.Option(..., help="Start date"),
    end: str = typer.Option(..., help="End date"),
    symbols: str | None = typer.Option(None, help="Comma separated symbols"),
    dry_run: bool = typer.Option(False, help="Only fetch and validate"),
) -> None:
    repo = Repository()
    adapter = FinMindAdapter(repo)
    sym_list = symbols.split(",") if symbols else []
    results = adapter.sync(SourceRequest(start=start, end=end, symbols=sym_list, dry_run=dry_run))
    _run_and_log(results, repo)


@sync_app.command("sec")
def sync_sec(
    tickers: str = typer.Option(..., help="Comma separated tickers"),
    date: str = typer.Option(datetime.now(UTC).strftime("%Y-%m-%d"), help="Run date"),
    dry_run: bool = typer.Option(False, help="Only fetch and validate"),
) -> None:
    repo = Repository()
    adapter = SecAdapter(repo)
    results = adapter.sync(
        SourceRequest(date=date, symbols=[x.strip() for x in tickers.split(",")], dry_run=dry_run)
    )
    _run_and_log(results, repo)


@sync_app.command("opendart")
def sync_opendart(
    symbols: str = typer.Option(..., help="Comma separated KR symbols"),
    date: str = typer.Option(datetime.now(UTC).strftime("%Y-%m-%d"), help="Run date"),
    dry_run: bool = typer.Option(False, help="Only fetch and validate"),
) -> None:
    repo = Repository()
    adapter = OpenDartAdapter(repo)
    results = adapter.sync(
        SourceRequest(date=date, symbols=[x.strip() for x in symbols.split(",")], dry_run=dry_run)
    )
    _run_and_log(results, repo)


@sync_app.command("global-anchors")
def sync_global_anchors(
    date: str = typer.Option(..., help="Trade date YYYY-MM-DD"),
    dry_run: bool = typer.Option(False, help="Only fetch and validate"),
) -> None:
    repo = Repository()
    repo.init_db()
    adapter = GlobalAnchorAdapter(repo)
    results = adapter.sync(SourceRequest(date=date, dry_run=dry_run))
    _run_and_log(results, repo)


@app.command("score")
def score(
    target: str | None = typer.Argument(
        None, help="Optional target: market-confirmation | global-anchors"
    ),
    date: str = typer.Option(..., help="Score date"),
    intraday: bool = typer.Option(False, "--intraday", help="Use intraday crowding features"),
) -> None:
    repo = Repository()
    repo.init_db()
    mode = (target or "").strip().lower()
    if mode in {"", "all"}:
        TradingConfirmationScore().run_segment_daily(repo=repo, score_date=date, intraday=intraday)
        scorer = OpportunityScore()
        rows = scorer.run(repo=repo, score_date=date)
        typer.echo(f"Generated {rows} segment scores for {date}.")
        return
    if mode == "market-confirmation":
        rows = _run_market_confirmation_only(repo=repo, date=date, intraday=intraday)
        typer.echo(f"Segment market confirmation rows generated: {rows}")
        return
    if mode == "global-anchors":
        rows = _run_global_anchor_score_only(repo=repo, date=date)
        typer.echo(f"Global anchor segment scores generated: {rows}")
        return
    raise typer.BadParameter(
        f"Unsupported score target: {target}. Use market-confirmation/global-anchors."
    )


@app.command("score-market-confirmation")
def score_market_confirmation(
    date: str = typer.Option(..., help="Trade date"),
    intraday: bool = typer.Option(False, "--intraday", help="Use intraday crowding features"),
) -> None:
    repo = Repository()
    repo.init_db()
    rows = _run_market_confirmation_only(repo=repo, date=date, intraday=intraday)
    typer.echo(f"Segment market confirmation rows generated: {rows}")


@app.command("score-global-anchors")
def score_global_anchors(
    date: str = typer.Option(..., help="Score date"),
) -> None:
    repo = Repository()
    repo.init_db()
    rows = _run_global_anchor_score_only(repo=repo, date=date)
    typer.echo(f"Global anchor segment scores generated: {rows}")


@app.command("brief")
def brief(
    date: str = typer.Option(..., help="Briefing date"),
    output_format: str = typer.Option("md", "--format", help="Output format, currently md only"),
    mode: str = typer.Option(
        "default", "--mode", help="Brief mode: default | premarket (layout note only)"
    ),
    with_review: bool = typer.Option(
        False, "--with-review", help="Auto-run review summary for the same date before rendering"
    ),
) -> None:
    if mode not in {"default", "premarket"}:
        raise typer.BadParameter("Unsupported mode, use default or premarket")
    repo = Repository()
    if with_review:
        review_rows = run_signal_review(repo=repo, review_date=date, lookback=10)
        if review_rows > 0:
            build_review_summary(repo=repo, review_date=date)
    path = render_daily_briefing(
        repo=repo,
        score_date=date,
        fmt=output_format,
        with_review=with_review,
    )
    typer.echo(f"Briefing generated: {path}")
    if mode == "premarket":
        typer.echo("Brief mode=premarket (same renderer, premarket workflow compatible).")


@import_app.command("mapping")
def import_mapping(
    file: str = typer.Option(..., "--file", help="Mapping CSV/XLSX file path"),
) -> None:
    repo = Repository()
    repo.init_db()
    try:
        result = MappingImporter(repo).import_file(file)
        _write_operation_log(
            repo=repo,
            source="mapping_importer",
            job_name="mapping",
            params={"file": file},
            status="ok",
            rows_read=result.row_count,
            rows_written=result.row_count,
        )
        typer.echo(
            "Imported mapping: "
            f"version={result.version_id} "
            f"rows={result.row_count} "
            f"checksum={result.checksum}"
        )
    except Exception as exc:
        _write_operation_log(
            repo=repo,
            source="mapping_importer",
            job_name="mapping",
            params={"file": file},
            status="failed",
            rows_read=0,
            rows_written=0,
            error_message=str(exc),
        )
        raise


@import_app.command("global-prices")
def import_global_prices(
    file: str = typer.Option(..., "--file", help="Global anchor price CSV/XLSX file path"),
    notes: str = typer.Option("", help="Import notes"),
) -> None:
    repo = Repository()
    repo.init_db()
    try:
        result = GlobalPriceImporter(repo).import_file(file, notes=notes)
        _write_operation_log(
            repo=repo,
            source="global_price_importer",
            job_name="global_prices",
            params={"file": file, "trade_date": result.trade_date},
            status="ok",
            rows_read=result.row_count,
            rows_written=result.row_count,
        )
        typer.echo(
            "Imported global prices: "
            f"import_id={result.import_id} "
            f"trade_date={result.trade_date} "
            f"rows={result.row_count} "
            f"checksum={result.checksum}"
        )
    except Exception as exc:
        _write_operation_log(
            repo=repo,
            source="global_price_importer",
            job_name="global_prices",
            params={"file": file},
            status="failed",
            rows_read=0,
            rows_written=0,
            error_message=str(exc),
        )
        raise


@extract_app.command("evidence")
def extract_evidence(date: str = typer.Option(..., help="Evidence date YYYY-MM-DD")) -> None:
    repo = Repository()
    repo.init_db()
    try:
        rows = extract_evidence_for_date(repo, date)
        _write_operation_log(
            repo=repo,
            source="evidence_extractor",
            job_name="extract_evidence",
            params={"date": date},
            status="ok" if rows > 0 else "empty",
            rows_read=rows,
            rows_written=rows,
        )
        typer.echo(f"Evidence extracted: {rows}")
    except Exception as exc:
        _write_operation_log(
            repo=repo,
            source="evidence_extractor",
            job_name="extract_evidence",
            params={"date": date},
            status="failed",
            rows_read=0,
            rows_written=0,
            error_message=str(exc),
        )
        raise


@evidence_app.command("list")
def evidence_list(
    segment: str | None = typer.Option(None, help="Filter by segment id"),
    limit: int = typer.Option(20, help="Max rows"),
) -> None:
    repo = Repository()
    repo.init_db()
    df = EvidenceRegistry(repo).list_latest(limit=limit, segment=segment)
    if df.empty:
        typer.echo("No evidence found.")
        return
    show_cols = [
        "evidence_id",
        "evidence_date",
        "source_type",
        "segment",
        "entity_id",
        "evidence_level",
        "claim",
    ]
    show = df[show_cols].copy()
    typer.echo(show.to_string(index=False))


@evidence_app.command("add")
def evidence_add(
    claim: str = typer.Option(..., help="Evidence claim text"),
    segment: str = typer.Option(..., help="Segment id"),
    sub_segment: str = typer.Option("", help="Sub segment"),
    evidence_level: str = typer.Option("C", help="Evidence level A1/A2/B/C/D"),
    entity_id: str = typer.Option("", help="Entity id (e.g. ts_code)"),
    entity_name: str = typer.Option("", help="Entity name"),
    source_url: str = typer.Option("", help="Source URL"),
    positive: bool = typer.Option(
        True,
        "--positive/--counter",
        help="Positive or counter evidence",
    ),
    notes: str = typer.Option("", help="Manual notes"),
) -> None:
    repo = Repository()
    repo.init_db()
    evidence_id = EvidenceRegistry(repo).add_manual(
        ManualEvidenceInput(
            claim=claim,
            segment=segment,
            sub_segment=sub_segment,
            evidence_level=evidence_level,
            entity_id=entity_id,
            entity_name=entity_name,
            source_url=source_url,
            is_positive=positive,
            notes=notes,
        )
    )
    typer.echo(f"Manual evidence added: {evidence_id}")


@app.command("review")
def review(
    date: str = typer.Option(..., help="Review date YYYY-MM-DD"),
    lookback: int = typer.Option(10, help="Lookback score rows"),
) -> None:
    repo = Repository()
    repo.init_db()
    rows = run_signal_review(repo=repo, review_date=date, lookback=lookback)
    summary_rows = build_review_summary(repo=repo, review_date=date) if rows > 0 else 0
    _write_operation_log(
        repo=repo,
        source="signal_review",
        job_name="review",
        params={"date": date, "lookback": lookback},
        status="ok" if rows > 0 else "empty",
        rows_read=rows,
        rows_written=rows,
    )
    typer.echo(f"Review rows generated: {rows}, summary rows generated: {summary_rows}")


@db_app.command("query")
def db_query(sql: str = typer.Argument(..., help="SQL query")) -> None:
    repo = Repository()
    repo.init_db()
    df = repo.query_dataframe(sql)
    if df.empty:
        typer.echo("(empty)")
        return
    typer.echo(df.to_string(index=False))


@db_app.command("clean-text")
def db_clean_text(
    apply: bool = typer.Option(
        False,
        "--apply",
        help="Apply updates to database. Without this flag, command runs in preview mode.",
    ),
) -> None:
    repo = Repository()
    repo.init_db()
    results = cleanup_mojibake_text(repo=repo, apply_changes=apply)
    mode = "apply" if apply else "preview"
    typer.echo(f"Text cleanup mode: {mode}")
    total_scanned = 0
    total_changed = 0
    for item in results:
        total_scanned += item.scanned_rows
        total_changed += item.changed_rows
        typer.echo(
            f"[{item.table}] scanned={item.scanned_rows} changed={item.changed_rows}"
        )
    typer.echo(f"Total scanned={total_scanned}, total changed={total_changed}")


@dq_app.command("report")
def dq_report(date: str = typer.Option(..., help="Report date YYYY-MM-DD")) -> None:
    repo = Repository()
    repo.init_db()
    rows = build_data_quality_report(repo=repo, report_date=date)
    _write_operation_log(
        repo=repo,
        source="dq_report",
        job_name="report",
        params={"date": date},
        status="ok" if rows > 0 else "empty",
        rows_read=rows,
        rows_written=rows,
    )
    typer.echo(f"Data quality rows generated: {rows}")


@dq_app.command("missing")
def dq_missing(date: str = typer.Option(..., help="Report date YYYY-MM-DD")) -> None:
    repo = Repository()
    repo.init_db()
    payload = build_missing_data_report(repo=repo, report_date=date)
    status = "ok" if payload["missing_anchor_count"] == 0 else "empty"
    _write_operation_log(
        repo=repo,
        source="missing_data_report",
        job_name="missing_data",
        params={"date": date},
        status=status,
        rows_read=payload["expected_anchor_count"],
        rows_written=payload["actual_anchor_count"],
    )
    typer.echo(
        f"Missing data report generated: {payload['markdown_path']} "
        f"(missing={payload['missing_anchor_count']})"
    )


@app.command("alert")
def alert(date: str = typer.Option(..., help="Alert date YYYY-MM-DD")) -> None:
    repo = Repository()
    repo.init_db()
    payload = build_alert_report(repo=repo, report_date=date)
    _write_operation_log(
        repo=repo,
        source="alert",
        job_name="daily_alert",
        params={"date": date},
        status="ok" if payload["alert_count"] > 0 else "empty",
        rows_read=payload["alert_count"],
        rows_written=payload["alert_count"],
    )
    typer.echo(f"Alert report generated: {payload['path']} (alerts={payload['alert_count']})")


@calibrate_app.command("scoring")
def calibrate_scoring(
    window: int = typer.Option(60, help="Number of recent review dates"),
    end_date: str = typer.Option("", "--end-date", help="Optional end date YYYY-MM-DD"),
) -> None:
    repo = Repository()
    repo.init_db()
    payload = export_scoring_calibration(
        repo=repo,
        window=max(1, window),
        end_date=end_date or None,
    )
    status = "ok" if payload["rows"] > 0 else "empty"
    _write_operation_log(
        repo=repo,
        source="calibration",
        job_name="scoring",
        params={"window": max(1, window), "end_date": end_date or None},
        status=status,
        rows_read=payload["rows"],
        rows_written=payload["rows"],
    )
    if payload["rows"] == 0:
        typer.echo("No review summary rows found for calibration.")
        return
    typer.echo(f"Scoring calibration exported: {payload['path']}")


@export_app.command("weekly-report")
def export_weekly_report_cmd(
    date: str = typer.Option(..., help="Week end date YYYY-MM-DD"),
) -> None:
    repo = Repository()
    repo.init_db()
    payload = export_weekly_report(repo=repo, end_date=date)
    total_rows = payload["score_rows"] + payload["review_rows"]
    _write_operation_log(
        repo=repo,
        source="export",
        job_name="weekly_report",
        params={"date": date},
        status="ok" if total_rows > 0 else "empty",
        rows_read=total_rows,
        rows_written=total_rows,
    )
    typer.echo(f"Weekly report exported: {payload['path']}")


@export_app.command("network-acceptance")
def export_network_acceptance_cmd(
    date: str = typer.Option(..., help="Acceptance date YYYY-MM-DD"),
    target_date: str = typer.Option("", "--target-date", help="Business date YYYY-MM-DD"),
    reviewer: str = typer.Option("Codex", help="Reviewer name"),
    ui_url: str = typer.Option("http://127.0.0.1:8000/ui", help="UI URL"),
    ui_screenshot_path: str = typer.Option(
        "", "--ui-screenshot", help="Optional UI screenshot path"
    ),
    max_log_rows: int = typer.Option(60, "--max-log-rows", help="Max run-log rows in output"),
) -> None:
    repo = Repository()
    repo.init_db()
    payload = export_network_acceptance_report(
        repo=repo,
        acceptance_date=date,
        target_date=target_date or None,
        reviewer=reviewer,
        ui_url=ui_url,
        ui_screenshot_path=ui_screenshot_path,
        max_log_rows=max(1, max_log_rows),
    )
    _write_operation_log(
        repo=repo,
        source="export",
        job_name="network_acceptance",
        params={
            "date": date,
            "target_date": target_date or None,
            "reviewer": reviewer,
            "ui_url": ui_url,
            "ui_screenshot_path": ui_screenshot_path or None,
            "max_log_rows": max(1, max_log_rows),
        },
        status="ok" if payload["overall_pass"] else "partial",
        rows_read=int(payload["score_count"]) + int(payload["review_count"]),
        rows_written=1,
    )
    typer.echo(
        f"Network acceptance report exported: {payload['path']} "
        f"(overall_pass={payload['overall_pass']})"
    )


@export_app.command("v02-audit")
def export_v02_audit_cmd(
    date: str = typer.Option(..., help="Business date YYYY-MM-DD"),
    reviewer: str = typer.Option("Codex", help="Reviewer name"),
    include_ci_gate: bool = typer.Option(
        True,
        "--include-ci-gate/--no-include-ci-gate",
        help="Check docs/CI_FIRST_RUN.md existence as a required gate",
    ),
) -> None:
    repo = Repository()
    repo.init_db()
    payload = export_v02_completion_audit(
        repo=repo,
        date=date,
        reviewer=reviewer,
        include_ci_gate=include_ci_gate,
    )
    _write_operation_log(
        repo=repo,
        source="export",
        job_name="v02_audit",
        params={
            "date": date,
            "reviewer": reviewer,
            "include_ci_gate": include_ci_gate,
        },
        status="ok" if payload["overall_pass"] else "partial",
        rows_read=int(payload["required_total"]),
        rows_written=1,
    )
    typer.echo(
        f"V0.2 completion audit exported: {payload['path']} "
        f"(required_pass={payload['required_passed']}/{payload['required_total']}, "
        f"overall_pass={payload['overall_pass']})"
    )


def main() -> None:
    try:
        app()
    except Exception as exc:  # pragma: no cover
        typer.echo(f"Error: {exc}")
        raise typer.Exit(code=1) from exc


if __name__ == "__main__":
    main()
