from __future__ import annotations

import hashlib
from datetime import UTC, datetime

import pandas as pd

from ai_chain_radar.db.repository import Repository
from ai_chain_radar.text_normalize import normalize_text


def extract_evidence_for_date(repo: Repository, trade_date: str) -> int:
    now = datetime.now(UTC).replace(tzinfo=None)
    rows: list[dict] = []

    rows.extend(_mapping_evidence_rows(repo, trade_date, now))
    rows.extend(_anchor_evidence_rows(repo, trade_date, now))
    rows.extend(_announcement_rows(repo, trade_date, now))
    rows.extend(_research_rows(repo, trade_date, now))
    rows.extend(_sec_rows(repo, trade_date, now))
    rows.extend(_opendart_rows(repo, trade_date, now))
    rows.extend(_finmind_rows(repo, trade_date, now))

    if not rows:
        return 0
    frame = pd.DataFrame(rows)
    return repo.upsert_dataframe("evidence_registry", frame, keys=["evidence_id"])


def _mapping_evidence_rows(repo: Repository, trade_date: str, now: datetime) -> list[dict]:
    segment_map = _load_segment_name_map(repo)
    mapping_df = repo.query_dataframe(
        """
        SELECT
          ts_code,
          name,
          segment,
          sub_segment,
          coalesce(source_evidence, '') AS source_evidence,
          coalesce(notes, '') AS notes,
          coalesce(counter_evidence_text, '') AS counter_evidence_text,
          coalesce(evidence_level, 'B') AS evidence_level
        FROM a_share_chain_mapping
        WHERE coalesce(is_latest, TRUE) = TRUE
        """
    )
    rows: list[dict] = []
    for item in mapping_df.itertuples(index=False):
        canonical_segment = _canonical_segment_id(
            raw_segment=str(item.segment or ""),
            segment_map=segment_map,
        )
        mapped_claim = f"{item.name} mapped to {item.segment}/{item.sub_segment}"
        claim = (
            normalize_text(item.notes)
            if str(item.notes).strip()
            else normalize_text(mapped_claim)
        )
        rows.append(
            _build_row(
                evidence_id=_stable_id(
                    "map", trade_date, item.ts_code, item.segment, item.sub_segment
                ),
                evidence_date=trade_date,
                source_type="manual_note",
                source_name="a_share_chain_mapping",
                source_url=str(item.source_evidence),
                source_title=f"mapping:{item.ts_code}",
                entity_id=item.ts_code,
                entity_name=normalize_text(item.name),
                segment=canonical_segment,
                sub_segment=item.sub_segment,
                evidence_level=item.evidence_level,
                claim=claim,
                confidence=0.8 if str(item.evidence_level).startswith("A") else 0.55,
                is_positive=True,
                is_counter=False,
                ingested_at=now,
                notes="seed mapping evidence",
            )
        )
        if str(item.counter_evidence_text).strip():
            rows.append(
                _build_row(
                    evidence_id=_stable_id(
                        "map_counter",
                        trade_date,
                        item.ts_code,
                        item.segment,
                        item.sub_segment,
                    ),
                    evidence_date=trade_date,
                    source_type="counter_evidence",
                    source_name="a_share_chain_mapping",
                    source_url=str(item.source_evidence),
                    source_title=f"counter:{item.ts_code}",
                    entity_id=item.ts_code,
                    entity_name=normalize_text(item.name),
                    segment=canonical_segment,
                    sub_segment=item.sub_segment,
                    evidence_level="D",
                    claim=normalize_text(str(item.counter_evidence_text)),
                    confidence=0.7,
                    is_positive=False,
                    is_counter=True,
                    ingested_at=now,
                    notes="mapping counter evidence",
                )
            )
    return rows


def _anchor_evidence_rows(repo: Repository, trade_date: str, now: datetime) -> list[dict]:
    df = repo.query_dataframe(
        """
        SELECT symbol, market, coalesce(pct_chg, 0.0) AS pct_chg
        FROM global_anchor_price_daily
        WHERE trade_date = ?
        """,
        [trade_date],
    )
    rows: list[dict] = []
    for item in df.itertuples(index=False):
        claim = f"{item.symbol}({item.market}) pct_chg={float(item.pct_chg):.2f}"
        rows.append(
            _build_row(
                evidence_id=_stable_id("anchor", trade_date, item.symbol, item.market),
                evidence_date=trade_date,
                source_type="global_anchor",
                source_name="global_anchor_price_daily",
                source_url="",
                source_title="anchor_move",
                entity_type="global_anchor",
                entity_id=item.symbol,
                entity_name=f"{item.symbol}({item.market})",
                segment="",
                sub_segment="",
                evidence_level="B",
                claim=claim,
                excerpt=claim,
                numeric_value=float(item.pct_chg),
                numeric_unit="pct_chg",
                confidence=0.7,
                is_positive=float(item.pct_chg) >= 0.0,
                is_counter=False,
                ingested_at=now,
            )
        )
    return rows


def _announcement_rows(repo: Repository, trade_date: str, now: datetime) -> list[dict]:
    ann_df = repo.query_dataframe(
        """
        SELECT ann_id, ann_date, ts_code, name, title, url
        FROM a_share_announcement_event
        WHERE ann_date = ?
        """,
        [trade_date],
    )
    rows: list[dict] = []
    for item in ann_df.itertuples(index=False):
        claim = normalize_text(item.title or "A-share announcement")
        rows.append(
            _build_row(
                evidence_id=_stable_id("ann", str(item.ann_id)),
                evidence_date=item.ann_date,
                source_type="company_filing",
                source_name="tushare.anns_d",
                source_url=item.url or "",
                source_title=claim,
                entity_id=item.ts_code or "",
                entity_name=normalize_text(item.name or ""),
                evidence_level="B",
                claim=claim,
                confidence=0.6,
                is_positive=True,
                is_counter=False,
                ingested_at=now,
            )
        )
    return rows


def _research_rows(repo: Repository, trade_date: str, now: datetime) -> list[dict]:
    report_df = repo.query_dataframe(
        """
        SELECT report_id, trade_date, ts_code, name, title, url
        FROM a_share_research_report_event
        WHERE trade_date = ?
        """,
        [trade_date],
    )
    rows: list[dict] = []
    for item in report_df.itertuples(index=False):
        claim = normalize_text(item.title or "Broker research report")
        rows.append(
            _build_row(
                evidence_id=_stable_id("research", str(item.report_id)),
                evidence_date=item.trade_date,
                source_type="research_report",
                source_name="tushare.research_report",
                source_url=item.url or "",
                source_title=claim,
                entity_id=item.ts_code or "",
                entity_name=normalize_text(item.name or ""),
                evidence_level="B",
                claim=claim,
                confidence=0.55,
                is_positive=True,
                is_counter=False,
                ingested_at=now,
            )
        )
    return rows


def _sec_rows(repo: Repository, trade_date: str, now: datetime) -> list[dict]:
    sec_df = repo.query_dataframe(
        """
        SELECT
          accession_number,
          symbol,
          company_name,
          form_type,
          filing_url,
          coalesce(impact_segments, '') AS impact_segments
        FROM us_sec_filing_event
        WHERE filing_date = ?
        """,
        [trade_date],
    )
    rows: list[dict] = []
    for item in sec_df.itertuples(index=False):
        claim = normalize_text(f"{item.company_name} {item.form_type} filing")
        rows.append(
            _build_row(
                evidence_id=_stable_id("sec", str(item.accession_number)),
                evidence_date=trade_date,
                source_type="company_filing",
                source_name="sec.filing",
                source_url=item.filing_url or "",
                source_title=str(item.form_type),
                entity_type="global_anchor",
                entity_id=item.symbol or "",
                entity_name=normalize_text(item.company_name or ""),
                segment=str(item.impact_segments or ""),
                evidence_level="A2",
                claim=claim,
                confidence=0.7,
                is_positive=True,
                is_counter=False,
                ingested_at=now,
            )
        )
    return rows


def _opendart_rows(repo: Repository, trade_date: str, now: datetime) -> list[dict]:
    kr_df = repo.query_dataframe(
        """
        SELECT rcept_no, stock_code, corp_name, report_nm, raw_url
        FROM korea_disclosure_event
        WHERE rcept_dt = ?
        """,
        [trade_date],
    )
    rows: list[dict] = []
    for item in kr_df.itertuples(index=False):
        claim = normalize_text(f"{item.corp_name} {item.report_nm}")
        rows.append(
            _build_row(
                evidence_id=_stable_id("opendart", str(item.rcept_no)),
                evidence_date=trade_date,
                source_type="company_filing",
                source_name="opendart.disclosure",
                source_url=item.raw_url or "",
                source_title=normalize_text(item.report_nm or ""),
                entity_type="global_anchor",
                entity_id=item.stock_code or "",
                entity_name=normalize_text(item.corp_name or ""),
                evidence_level="A2",
                claim=claim,
                confidence=0.65,
                is_positive=True,
                is_counter=False,
                ingested_at=now,
            )
        )
    return rows


def _finmind_rows(repo: Repository, trade_date: str, now: datetime) -> list[dict]:
    month = trade_date[:7]
    tw_df = repo.query_dataframe(
        """
        SELECT symbol, coalesce(revenue_mom, 0.0) AS revenue_mom, coalesce(revenue, 0.0) AS revenue
        FROM taiwan_monthly_revenue
        WHERE revenue_month = ?
        """,
        [month],
    )
    rows: list[dict] = []
    for item in tw_df.itertuples(index=False):
        positive = float(item.revenue_mom) >= 0.0
        claim = f"TW revenue_mom={float(item.revenue_mom):.2f}, revenue={float(item.revenue):.0f}"
        rows.append(
            _build_row(
                evidence_id=_stable_id("finmind_revenue", month, item.symbol),
                evidence_date=trade_date,
                source_type="financial_metric",
                source_name="finmind.TaiwanStockMonthRevenue",
                source_title="monthly_revenue",
                entity_type="global_anchor",
                entity_id=item.symbol,
                entity_name=item.symbol,
                evidence_level="B",
                claim=claim,
                excerpt=claim,
                numeric_value=float(item.revenue_mom),
                numeric_unit="revenue_mom",
                confidence=0.6,
                is_positive=positive,
                is_counter=not positive,
                ingested_at=now,
                notes="counter when revenue_mom < 0",
            )
        )
    return rows


def _build_row(
    *,
    evidence_id: str,
    evidence_date: str,
    source_type: str,
    source_name: str,
    claim: str,
    ingested_at: datetime,
    source_url: str = "",
    source_file: str = "",
    source_title: str = "",
    entity_type: str = "a_share",
    entity_id: str = "",
    entity_name: str = "",
    segment: str = "",
    sub_segment: str = "",
    evidence_level: str = "B",
    excerpt: str = "",
    numeric_value: float | None = None,
    numeric_unit: str = "",
    confidence: float = 0.5,
    is_positive: bool = True,
    is_counter: bool = False,
    verified_by: str = "",
    notes: str = "",
) -> dict:
    return {
        "evidence_id": evidence_id,
        "evidence_date": evidence_date,
        "source_type": source_type,
        "source_name": source_name,
        "source_url": source_url,
        "source_file": source_file,
        "source_title": source_title,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "entity_name": entity_name,
        "segment": segment,
        "sub_segment": sub_segment,
        "evidence_level": evidence_level,
        "claim": claim,
        "excerpt": excerpt or claim,
        "numeric_value": numeric_value,
        "numeric_unit": numeric_unit,
        "confidence": confidence,
        "is_positive": is_positive,
        "is_counter_evidence": is_counter,
        "ingested_at": ingested_at,
        "verified_by": verified_by,
        "notes": notes,
    }


def _stable_id(prefix: str, *parts: str) -> str:
    raw = "|".join([prefix, *[str(p) for p in parts]])
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]  # noqa: S324
    return f"{prefix}_{digest}"


def _load_segment_name_map(repo: Repository) -> dict[str, str]:
    df = repo.query_dataframe("SELECT segment_id, segment_name FROM ai_chain_segment")
    return {str(row.segment_id): str(row.segment_name) for row in df.itertuples(index=False)}


def _canonical_segment_id(raw_segment: str, segment_map: dict[str, str]) -> str:
    seg = normalize_text(str(raw_segment or "").strip())
    if not seg:
        return ""
    if seg in segment_map:
        return seg

    pairs = [
        ("hbm_storage", ["hbm", "存储"]),
        ("cowos_advanced_packaging", ["cowos", "封装", "chiplet"]),
        ("optics_cpo_16t", ["cpo", "硅光", "光互连", "光模块"]),
        ("pcb_connector", ["pcb", "ccl", "连接器", "铜缆", "基板"]),
        ("liquid_cooling_power", ["液冷", "电力", "ups", "温控", "服务器", "数据中心"]),
    ]
    lower_seg = seg.lower()
    for canonical, keywords in pairs:
        if canonical not in segment_map:
            continue
        if any(keyword in seg or keyword in lower_seg for keyword in keywords):
            return canonical

    for segment_id, segment_name in segment_map.items():
        if seg == segment_name or seg in segment_name or segment_name in seg:
            return segment_id
    return seg
