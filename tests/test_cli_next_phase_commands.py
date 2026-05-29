from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from ai_chain_radar.cli import app
from ai_chain_radar.db.repository import Repository
from ai_chain_radar.scoring.opportunity_score import OpportunityScore
from ai_chain_radar.taxonomy.mapping import load_taxonomy


def test_import_global_prices_cli(tmp_path: Path) -> None:
    csv_path = tmp_path / "global_prices.csv"
    csv_path.write_text(
        "\n".join(
            [
                "trade_date,symbol,market,open,high,low,close,volume,source",
                "2026-05-28,NVDA,US,100,110,95,108,1000000,manual",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    runner = CliRunner()
    result = runner.invoke(app, ["import", "global-prices", "--file", str(csv_path)])
    assert result.exit_code == 0

    repo = Repository()
    repo.init_db()
    out = repo.query_dataframe("SELECT COUNT(*) AS c FROM global_anchor_price_daily")
    assert int(out.iloc[0]["c"]) == 1
    imp = repo.query_dataframe("SELECT COUNT(*) AS c FROM global_anchor_manual_price_import")
    assert int(imp.iloc[0]["c"]) == 1


def test_sync_global_anchors_dry_run_cli() -> None:
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["sync", "global-anchors", "--date", "2026-05-28", "--dry-run"],
    )
    assert result.exit_code == 0
    assert "status=skipped" in result.stdout


def test_missing_alert_calibrate_export_commands() -> None:
    repo = Repository()
    repo.init_db()
    load_taxonomy(repo)
    repo.query_dataframe(
        """
        INSERT INTO theme_opportunity_score (
          score_date, segment, industry_score, bottleneck_score, global_anchor_score,
          earnings_order_price_score, a_share_mapping_score, a_share_confirmation_score,
          crowding_score, risk_score, final_score, stage, conclusion, evidence_json,
          invalid_conditions_json, created_at
        ) VALUES (
          '2026-05-28', 'hbm_storage', 70, 70, 70, 70, 70, 30, 90, 40, 80,
          'start', 'test', '[]', '["counter-evidence"]', now()
        )
        """
    )
    repo.query_dataframe(
        """
        INSERT INTO signal_review_summary (
          summary_id, review_date, segment, sample_count, true_positive, false_positive,
          false_negative, precision, recall, avg_forward_return_3d, avg_forward_return_10d,
          created_at
        ) VALUES (
          'sum_1', '2026-05-28', 'hbm_storage', 10, 6, 2, 1, 0.75, 0.86, 1.2, 2.8, now()
        )
        """
    )

    runner = CliRunner()
    dq_result = runner.invoke(app, ["dq", "missing", "--date", "2026-05-28"])
    assert dq_result.exit_code == 0

    alert_result = runner.invoke(app, ["alert", "--date", "2026-05-28"])
    assert alert_result.exit_code == 0

    cal_result = runner.invoke(app, ["calibrate", "scoring", "--window", "10"])
    assert cal_result.exit_code == 0

    export_result = runner.invoke(app, ["export", "weekly-report", "--date", "2026-05-28"])
    assert export_result.exit_code == 0

    assert Path("data/reports/missing_data_2026-05-28.md").exists()
    assert Path("data/alerts/2026-05-28.md").exists()
    assert Path("data/reports/calibration_scoring_2026-05-28.md").exists()
    assert Path("data/reports/weekly/weekly_report_2026-05-28.md").exists()


def test_brief_with_review_flag() -> None:
    repo = Repository()
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

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "brief",
            "--date",
            "2026-05-28",
            "--format",
            "md",
            "--mode",
            "premarket",
            "--with-review",
        ],
    )
    assert result.exit_code == 0
    assert Path("data/briefings/2026-05-28.md").exists()


def test_sync_tushare_mode_flags() -> None:
    runner = CliRunner()
    events_result = runner.invoke(
        app,
        ["sync", "tushare", "--date", "2026-05-28", "--dry-run", "--events-only"],
    )
    assert events_result.exit_code == 0
    assert "[tushare:anns_d]" in events_result.stdout
    assert "[tushare:research_report]" in events_result.stdout
    assert "[tushare:report_rc]" in events_result.stdout

    realtime_result = runner.invoke(
        app,
        ["sync", "tushare", "--date", "2026-05-28", "--dry-run", "--realtime"],
    )
    assert realtime_result.exit_code == 0
    assert "[tushare:daily]" in realtime_result.stdout
    assert "[tushare:moneyflow]" in realtime_result.stdout

    invalid_result = runner.invoke(
        app,
        [
            "sync",
            "tushare",
            "--date",
            "2026-05-28",
            "--dry-run",
            "--events-only",
            "--realtime",
        ],
    )
    assert invalid_result.exit_code != 0


def test_score_target_compat_commands() -> None:
    repo = Repository()
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

    runner = CliRunner()
    mc_result = runner.invoke(
        app,
        ["score", "market-confirmation", "--date", "2026-05-28", "--intraday"],
    )
    assert mc_result.exit_code == 0
    assert "Segment market confirmation rows generated" in mc_result.stdout

    ga_result = runner.invoke(
        app,
        ["score", "global-anchors", "--date", "2026-05-28"],
    )
    assert ga_result.exit_code == 0
    assert "Global anchor segment scores generated" in ga_result.stdout

    alias_result = runner.invoke(
        app,
        ["score-global-anchors", "--date", "2026-05-28"],
    )
    assert alias_result.exit_code == 0


def test_export_network_acceptance_command() -> None:
    repo = Repository()
    repo.init_db()
    load_taxonomy(repo)
    repo.query_dataframe(
        """
        INSERT INTO source_run_log (
          run_id, source, job_name, started_at, ended_at,
          status, rows_read, rows_written, error_message, params_json
        ) VALUES (
          'run_acceptance_1', 'tushare', 'daily', timestamp '2026-05-29 10:00:00',
          timestamp '2026-05-29 10:01:00', 'ok', 10, 10, NULL, '{}'
        )
        """
    )
    repo.query_dataframe(
        """
        INSERT INTO source_run_log (
          run_id, source, job_name, started_at, ended_at,
          status, rows_read, rows_written, error_message, params_json
        ) VALUES (
          'run_acceptance_2', 'sec', 'filings', timestamp '2026-05-29 11:00:00',
          timestamp '2026-05-29 11:01:00', 'ok', 11, 11, NULL, '{}'
        )
        """
    )
    repo.query_dataframe(
        """
        INSERT INTO theme_opportunity_score (
          score_date, segment, industry_score, bottleneck_score, global_anchor_score,
          earnings_order_price_score, a_share_mapping_score, a_share_confirmation_score,
          crowding_score, risk_score, final_score, stage, conclusion, evidence_json,
          invalid_conditions_json, created_at
        ) VALUES (
          '2026-05-28', 'hbm_storage', 70, 70, 70, 70, 70, 70, 50, 50, 75,
          'start', 'test', '[]', '[]', now()
        )
        """
    )
    repo.query_dataframe(
        """
        INSERT INTO signal_review_summary (
          summary_id, review_date, segment, sample_count, true_positive,
          false_positive, false_negative, precision, recall,
          avg_forward_return_3d, avg_forward_return_10d, created_at
        ) VALUES (
          'summary_acceptance_1', '2026-05-28', 'hbm_storage', 5, 4, 1, 1, 0.8, 0.8, 1.2, 2.2, now()
        )
        """
    )
    Path("data/briefings").mkdir(parents=True, exist_ok=True)
    Path("data/briefings/2026-05-28.md").write_text("# brief\n", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "export",
            "network-acceptance",
            "--date",
            "2026-05-29",
            "--target-date",
            "2026-05-28",
            "--reviewer",
            "Codex",
            "--max-log-rows",
            "1",
        ],
    )
    assert result.exit_code == 0
    out_path = Path("docs/NETWORK_ACCEPTANCE_2026-05-29.md")
    assert out_path.exists()
    text = out_path.read_text(encoding="utf-8")
    assert "showing latest 1 rows only" in text


def test_export_v02_audit_command() -> None:
    repo = Repository()
    repo.init_db()
    load_taxonomy(repo)
    repo.query_dataframe(
        """
        INSERT INTO a_share_chain_mapping_version (
          version_id, source_file, imported_at, row_count, checksum, notes
        ) VALUES (
          'ver_v02_1', 'seed.csv', now(), 2, 'abc', 'test'
        )
        """
    )
    repo.query_dataframe(
        """
        INSERT INTO a_share_chain_mapping (
          ts_code, name, segment, sub_segment, purity_level, is_core, confidence_score
        ) VALUES
          ('300308.SZ', 'test1', 'hbm_storage', 'sub1', 'high', TRUE, 0.8),
          ('688256.SH', 'test2', 'hbm_storage', 'sub2', 'high', TRUE, 0.7)
        """
    )
    repo.query_dataframe(
        """
        INSERT INTO evidence_registry (
          evidence_id, evidence_date, source_type, entity_id, segment, claim,
          is_positive, is_counter_evidence, ingested_at
        ) VALUES
          (
            'ev_pos_1', '2026-05-28', 'manual_note',
            '300308.SZ', 'hbm_storage', 'pos1', TRUE, FALSE, now()
          ),
          (
            'ev_pos_2', '2026-05-28', 'manual_note',
            '688256.SH', 'hbm_storage', 'pos2', TRUE, FALSE, now()
          ),
          (
            'ev_neg_1', '2026-05-28', 'counter_evidence',
            '300308.SZ', 'hbm_storage', 'neg1', FALSE, TRUE, now()
          )
        """
    )
    repo.query_dataframe(
        """
        INSERT INTO source_run_log (
          run_id, source, job_name, started_at, ended_at,
          status, rows_read, rows_written, error_message, params_json
        ) VALUES
          (
            'run_v02_tushare', 'tushare', 'daily',
            timestamp '2026-05-28 10:00:00',
            timestamp '2026-05-28 10:00:10',
            'ok', 1, 1, NULL, '{}'
          ),
          (
            'run_v02_dq', 'dq_report', 'report',
            timestamp '2026-05-28 11:00:00',
            timestamp '2026-05-28 11:00:10',
            'ok', 1, 1, NULL, '{}'
          )
        """
    )
    repo.query_dataframe(
        """
        INSERT INTO theme_opportunity_score (
          score_date, segment, industry_score, bottleneck_score, global_anchor_score,
          earnings_order_price_score, a_share_mapping_score, a_share_confirmation_score,
          crowding_score, risk_score, final_score, stage, conclusion, evidence_json,
          invalid_conditions_json, created_at
        ) VALUES
          (
            '2026-05-28', 'hbm_storage', 70, 70, 70, 70, 70, 70,
            60, 50, 75, 'start', 'ok', '[]', '[]', now()
          ),
          (
            '2026-05-28', 'cowos_advanced_packaging', 70, 70, 70, 70, 70, 70,
            60, 50, 75, 'start', 'ok', '[]', '[]', now()
          ),
          (
            '2026-05-28', 'optics_cpo_16t', 70, 70, 70, 70, 70, 70,
            60, 50, 75, 'start', 'ok', '[]', '[]', now()
          ),
          (
            '2026-05-28', 'pcb_connector', 70, 70, 70, 70, 70, 70,
            60, 50, 75, 'start', 'ok', '[]', '[]', now()
          ),
          (
            '2026-05-28', 'liquid_cooling_power', 70, 70, 70, 70, 70, 70,
            60, 50, 75, 'start', 'ok', '[]', '[]', now()
          )
        """
    )
    repo.query_dataframe(
        """
        INSERT INTO signal_review_result (
          review_id, signal_date, review_date, segment, original_stage, original_score, created_at
        ) VALUES
          ('rv02_1', '2026-05-27', '2026-05-28', 'hbm_storage', 'start', 70, now())
        """
    )
    Path("data/briefings").mkdir(parents=True, exist_ok=True)
    Path("data/briefings/2026-05-28.md").write_text(
        "\n".join(
            [
                "# brief",
                "## 昨日判断复盘",
                "## 反证与风险",
                "## 明日观察",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "export",
            "v02-audit",
            "--date",
            "2026-05-28",
            "--reviewer",
            "Codex",
            "--no-include-ci-gate",
        ],
    )
    assert result.exit_code == 0
    out_path = Path("docs/V0_2_COMPLETION_AUDIT_2026-05-28.md")
    assert out_path.exists()
    text = out_path.read_text(encoding="utf-8")
    assert "Checklist" in text
    assert "required_pass" in text
