from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ai_chain_radar.db.repository import Repository
from ai_chain_radar.text_normalize import normalize_text


@dataclass(frozen=True)
class TextCleanupResult:
    table: str
    scanned_rows: int
    changed_rows: int


_TEXT_CLEANUP_TARGETS: list[dict[str, Any]] = [
    {
        "table": "a_share_announcement_event",
        "keys": ["ann_id"],
        "text_columns": ["name", "title"],
    },
    {
        "table": "a_share_research_report_event",
        "keys": ["report_id"],
        "text_columns": ["name", "title", "author", "inst_csname", "ind_name"],
    },
    {
        "table": "a_share_report_rating_event",
        "keys": ["rating_id"],
        "text_columns": [
            "name",
            "report_title",
            "report_type",
            "classify",
            "org_name",
            "author_name",
        ],
    },
    {
        "table": "evidence_registry",
        "keys": ["evidence_id"],
        "text_columns": ["source_title", "entity_name", "claim", "excerpt", "notes"],
    },
]


def cleanup_mojibake_text(repo: Repository, apply_changes: bool = False) -> list[TextCleanupResult]:
    results: list[TextCleanupResult] = []
    for target in _TEXT_CLEANUP_TARGETS:
        table = str(target["table"])
        keys = list(target["keys"])
        text_columns = list(target["text_columns"])

        select_cols = ", ".join([*keys, *text_columns])
        df = repo.query_dataframe(f"SELECT {select_cols} FROM {table}")
        scanned_rows = int(len(df.index))
        changed_rows = 0
        if df.empty:
            results.append(
                TextCleanupResult(table=table, scanned_rows=scanned_rows, changed_rows=changed_rows)
            )
            continue

        for row in df.to_dict(orient="records"):
            changed_payload: dict[str, str] = {}
            for col in text_columns:
                original = row.get(col)
                if original is None:
                    continue
                original_text = str(original)
                fixed_text = normalize_text(original_text)
                if fixed_text != original_text:
                    changed_payload[col] = fixed_text
            if not changed_payload:
                continue
            changed_rows += 1
            if not apply_changes:
                continue
            _update_row(repo=repo, table=table, keys=keys, row=row, payload=changed_payload)

        results.append(
            TextCleanupResult(table=table, scanned_rows=scanned_rows, changed_rows=changed_rows)
        )
    return results


def _update_row(
    *,
    repo: Repository,
    table: str,
    keys: list[str],
    row: dict[str, Any],
    payload: dict[str, str],
) -> None:
    set_clause = ", ".join([f"{col} = ?" for col in payload.keys()])
    where_clause = " AND ".join([f"{key} = ?" for key in keys])
    params = [*payload.values(), *[row[key] for key in keys]]
    repo.execute(
        f"UPDATE {table} SET {set_clause} WHERE {where_clause}",
        params,
    )
