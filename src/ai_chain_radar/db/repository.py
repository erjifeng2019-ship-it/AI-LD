from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import duckdb
import pandas as pd

from ai_chain_radar.db.duckdb import get_connection
from ai_chain_radar.sources.base import SyncResult


class Repository:
    def __init__(self, conn: duckdb.DuckDBPyConnection | None = None) -> None:
        self.conn = conn or get_connection()

    def init_db(self, schema_path: str | Path | None = None) -> None:
        path = Path(schema_path or Path(__file__).with_name("schema.sql"))
        sql = path.read_text(encoding="utf-8")
        self.conn.execute(sql)
        self._migrate_columns()

    def _migrate_columns(self) -> None:
        self._ensure_columns(
            "a_share_chain_mapping",
            [
                ("version_id", "TEXT"),
                ("is_latest", "BOOLEAN DEFAULT TRUE"),
                ("evidence_level", "TEXT"),
                ("source_url", "TEXT"),
                ("claim", "TEXT"),
                ("counter_evidence_text", "TEXT"),
                ("key_validation_metrics", "TEXT"),
                ("domestic_substitution", "TEXT"),
                ("nvidia_relation", "TEXT"),
                ("mass_production_status", "TEXT"),
                ("confidence_score", "DOUBLE"),
            ],
        )
        self._ensure_columns(
            "signal_review_result",
            [
                ("forward_return_10d", "DOUBLE"),
                ("was_false_negative", "BOOLEAN"),
            ],
        )
        self._ensure_columns(
            "theme_opportunity_score",
            [
                ("confidence_score", "DOUBLE"),
            ],
        )

    def _ensure_columns(self, table_name: str, columns: list[tuple[str, str]]) -> None:
        exists = self.conn.execute("SHOW TABLES").fetchdf()
        if table_name not in set(exists["name"].tolist()):
            return
        info = self.conn.execute(f"PRAGMA table_info('{table_name}')").fetchdf()
        current = set(info["name"].tolist())
        for col_name, col_type in columns:
            if col_name in current:
                continue
            self.conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type}")

    def upsert_dataframe(self, table_name: str, df: pd.DataFrame, keys: list[str]) -> int:
        if df.empty:
            return 0

        table_cols_df = self.conn.execute(f"PRAGMA table_info('{table_name}')").fetchdf()
        table_cols = table_cols_df["name"].tolist()
        use_cols = [col for col in df.columns if col in table_cols]
        if not use_cols:
            raise ValueError(f"No matching columns for table {table_name}")
        for key in keys:
            if key not in use_cols:
                raise ValueError(f"Missing key column `{key}` for table {table_name}")

        input_df = df[use_cols].drop_duplicates(subset=keys, keep="last")
        if input_df.empty:
            return 0

        temp_name = f"_tmp_{table_name}_{uuid4().hex[:8]}"
        self.conn.register("_tmp_input_df", input_df)
        self.conn.execute(f"CREATE TEMP TABLE {temp_name} AS SELECT * FROM _tmp_input_df")
        on_cond = " AND ".join([f"t.{k}=s.{k}" for k in keys])
        self.conn.execute(f"DELETE FROM {table_name} AS t USING {temp_name} AS s WHERE {on_cond}")
        cols_csv = ", ".join(use_cols)
        self.conn.execute(
            f"INSERT INTO {table_name} ({cols_csv}) SELECT {cols_csv} FROM {temp_name}"
        )
        self.conn.execute(f"DROP TABLE {temp_name}")
        self.conn.unregister("_tmp_input_df")
        return len(input_df)

    def write_run_log(self, result: SyncResult) -> None:
        payload = asdict(result)
        params_json = json.dumps(payload["params"], ensure_ascii=False)
        self.conn.execute(
            """
            INSERT INTO source_run_log (
                run_id, source, job_name, started_at, ended_at, status, rows_read, rows_written,
                error_message, params_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                result.run_id,
                result.source,
                result.dataset,
                result.started_at,
                result.ended_at,
                result.status,
                result.rows_read,
                result.rows_written,
                result.error_message,
                params_json,
            ],
        )

    def query_dataframe(self, sql: str, params: list[Any] | None = None) -> pd.DataFrame:
        if params is None:
            return self.conn.execute(sql).fetchdf()
        return self.conn.execute(sql, params).fetchdf()

    def execute(self, sql: str, params: list[Any] | None = None) -> None:
        if params is None:
            self.conn.execute(sql)
            return
        self.conn.execute(sql, params)

    def close(self) -> None:
        try:
            self.conn.close()
        except Exception:
            pass

    def __enter__(self) -> Repository:
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close()

    @staticmethod
    def now_ts() -> datetime:
        return datetime.now(UTC).replace(tzinfo=None)
