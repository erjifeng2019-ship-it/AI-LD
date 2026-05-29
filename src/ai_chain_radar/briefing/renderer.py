from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd
from jinja2 import Environment, FileSystemLoader

from ai_chain_radar.db.repository import Repository
from ai_chain_radar.text_normalize import normalize_text


def render_daily_briefing(
    repo: Repository, score_date: str, fmt: str = "md", with_review: bool = False
) -> Path:
    if fmt != "md":
        raise ValueError("Only markdown format is supported.")
    score_df = repo.query_dataframe(
        """
        SELECT *
        FROM theme_opportunity_score
        WHERE score_date = ?
        ORDER BY final_score DESC
        """,
        [score_date],
    )
    if score_df.empty:
        raise ValueError(f"No score rows found for {score_date}. Run `ai-chain score` first.")

    top = score_df.head(5).copy()
    top["final_score"] = top["final_score"].round(2)
    top["industry_score"] = top["industry_score"].round(2)
    top["a_share_confirmation_score"] = top["a_share_confirmation_score"].round(2)
    top["crowding"] = top["crowding_score"].round(2)
    watch = score_df[score_df["final_score"].between(55, 70, inclusive="left")]
    risks = _collect_risks(top)
    evidence_refs = _collect_evidence_refs(top)
    evidence_quality = _evidence_quality(top)

    context = {
        "score_date": score_date,
        "with_review": with_review,
        "summary": _summary(top),
        "top_segments": top.to_dict(orient="records"),
        "watch_segments": watch.to_dict(orient="records"),
        "anchor_moves": _anchor_notes(repo, score_date),
        "taiwan_note": _taiwan_note(repo),
        "korea_note": _korea_note(repo),
        "japan_note": "MVP 暂无日本独立数据源，使用全球锚点替代。",
        "risks": risks,
        "evidence_refs": evidence_refs,
        "evidence_quality": evidence_quality,
        "review_summary": _review_summary(repo, score_date),
        "review_rows": _review_rows(repo, score_date),
    }

    env = Environment(
        loader=FileSystemLoader(str(Path(__file__).parent / "templates")),
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template("daily_briefing.md.j2")
    markdown = template.render(**context)

    out_dir = Path("data/briefings")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{score_date}.md"
    out_path.write_text(markdown, encoding="utf-8")
    latest_path = out_dir / "latest.md"
    latest_path.write_text(markdown, encoding="utf-8")

    repo.upsert_dataframe(
        "daily_ai_chain_briefing",
        pd.DataFrame(
            [
                {
                    "briefing_date": score_date,
                    "global_chain_conclusion": context["summary"]["status"],
                    "top_segments_json": json.dumps(
                        context["top_segments"], ensure_ascii=False, default=str
                    ),
                    "next_watch_segments_json": json.dumps(
                        context["watch_segments"], ensure_ascii=False, default=str
                    ),
                    "a_share_confirmed_segments_json": json.dumps(
                        context["top_segments"], ensure_ascii=False, default=str
                    ),
                    "risk_segments_json": json.dumps(risks, ensure_ascii=False),
                    "action_suggestion": "优先关注主线扩散与资金确认，避免追高。",
                    "evidence_json": json.dumps(
                        {
                            "anchor_moves": context["anchor_moves"],
                            "evidence_refs": evidence_refs,
                            "evidence_quality": evidence_quality,
                        },
                        ensure_ascii=False,
                    ),
                    "invalid_conditions_json": json.dumps(risks, ensure_ascii=False),
                    "markdown_path": str(out_path),
                    "created_at": datetime.now(UTC).replace(tzinfo=None),
                }
            ]
        ),
        keys=["briefing_date"],
    )
    return out_path


def _summary(top_df: pd.DataFrame) -> dict[str, Any]:
    mean_score = float(top_df["final_score"].mean())
    status = "主升/启动" if mean_score >= 70 else "预热/观察"
    risk = "中高" if float(top_df["crowding"].max()) > 75 else "中低"
    return {
        "status": status,
        "industry_score": round(float(top_df["industry_score"].mean()), 2),
        "confirmation_score": round(float(top_df["a_share_confirmation_score"].mean()), 2),
        "crowding": round(float(top_df["crowding"].mean()), 2),
        "risk_level": risk,
    }


def _collect_risks(top_df: pd.DataFrame) -> list[str]:
    risks: list[str] = []
    for row in top_df.itertuples(index=False):
        raw = getattr(row, "invalid_conditions_json", None)
        if not raw:
            continue
        try:
            items = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, str):
                continue
            text = item.strip()
            if text and text not in risks:
                risks.append(text)
    if risks:
        return risks[:12]
    return ["当前未命中显著反证规则，继续跟踪成交确认与拥挤度。"]


def _collect_evidence_refs(top_df: pd.DataFrame) -> list[dict[str, str]]:
    refs: list[dict[str, str]] = []
    seen_ids: set[str] = set()
    for row in top_df.itertuples(index=False):
        raw = getattr(row, "evidence_json", None)
        if not raw:
            continue
        try:
            items = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            evidence_id = str(item.get("evidence_id", "")).strip()
            if not evidence_id or evidence_id in seen_ids:
                continue
            seen_ids.add(evidence_id)
            refs.append(
                {
                    "evidence_id": evidence_id,
                    "source": normalize_text(str(item.get("source", ""))),
                    "message": normalize_text(str(item.get("message", "")).strip()),
                }
            )
            if len(refs) >= 20:
                return refs
    return refs


def _evidence_quality(top_df: pd.DataFrame) -> dict[str, list[dict[str, str]] | int]:
    source_count: dict[str, int] = {}
    level_count: dict[str, int] = {}
    total = 0

    for row in top_df.itertuples(index=False):
        raw = getattr(row, "evidence_json", None)
        if not raw:
            continue
        try:
            items = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            total += 1
            source = str(item.get("source", "")).strip() or "unknown"
            level = str(item.get("evidence_level", "")).strip() or "unlabeled"
            source_count[source] = source_count.get(source, 0) + 1
            level_count[level] = level_count.get(level, 0) + 1

    top_sources = sorted(source_count.items(), key=lambda kv: kv[1], reverse=True)[:6]
    top_levels = sorted(level_count.items(), key=lambda kv: kv[1], reverse=True)[:6]
    return {
        "total_items": total,
        "source_breakdown": [{"name": k, "count": str(v)} for k, v in top_sources],
        "level_breakdown": [{"name": k, "count": str(v)} for k, v in top_levels],
    }


def _anchor_notes(repo: Repository, score_date: str) -> list[str]:
    df = repo.query_dataframe(
        """
        SELECT symbol, market, pct_chg
        FROM global_anchor_price_daily
        WHERE trade_date = ?
        ORDER BY abs(coalesce(pct_chg, 0)) DESC
        LIMIT 5
        """,
        [score_date],
    )
    if df.empty:
        return ["暂无全球锚点行情，待数据同步。"]
    return [f"{r.symbol}({r.market}) 涨跌 {r.pct_chg}" for r in df.itertuples(index=False)]


def _taiwan_note(repo: Repository) -> str:
    df = repo.query_dataframe("SELECT count(*) AS cnt FROM taiwan_monthly_revenue")
    return "已获取样本" if int(df.iloc[0]["cnt"]) > 0 else "暂无月营收样本"


def _korea_note(repo: Repository) -> str:
    df = repo.query_dataframe("SELECT count(*) AS cnt FROM korea_disclosure_event")
    return "已获取披露样本" if int(df.iloc[0]["cnt"]) > 0 else "暂无韩国披露样本"


def _review_rows(repo: Repository, score_date: str) -> list[dict[str, Any]]:
    df = repo.query_dataframe(
        """
        SELECT
          segment,
          original_stage,
          original_score,
          forward_return_1d,
          forward_return_3d,
          forward_return_5d,
          was_confirmed
        FROM signal_review_result
        WHERE review_date = ?
        ORDER BY original_score DESC
        LIMIT 5
        """,
        [score_date],
    )
    if df.empty:
        return []
    return df.to_dict(orient="records")


def _review_summary(repo: Repository, score_date: str) -> str:
    df = repo.query_dataframe(
        """
        SELECT
          count(*) AS total_cnt,
          sum(CASE WHEN coalesce(was_confirmed, FALSE) THEN 1 ELSE 0 END) AS confirmed_cnt
        FROM signal_review_result
        WHERE review_date = ?
        """,
        [score_date],
    )
    if df.empty or int(df.iloc[0]["total_cnt"] or 0) == 0:
        return "暂无复盘记录（请先执行 ai-chain review）。"
    total = int(df.iloc[0]["total_cnt"] or 0)
    confirmed = int(df.iloc[0]["confirmed_cnt"] or 0)
    return f"复盘样本 {total} 条，确认 {confirmed} 条。"
