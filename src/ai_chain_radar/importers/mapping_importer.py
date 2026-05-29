from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pandas as pd

from ai_chain_radar.db.repository import Repository


@dataclass
class MappingImportResult:
    version_id: str
    row_count: int
    checksum: str
    source_file: str


class MappingImporter:
    REQUIRED_COLUMNS = {
        "ts_code",
        "name",
        "segment",
        "sub_segment",
        "purity_level",
        "evidence_level",
    }

    COLUMN_ALIASES = {
        "股票代码": "ts_code",
        "A股公司": "name",
        "Level1_大类": "segment",
        "Level2_细分环节": "sub_segment",
        "Level3_具体产品/工艺": "product",
        "映射类型": "mapping_type",
        "国产替代属性": "domestic_substitution",
        "英伟达关系_严格口径": "nvidia_relation",
        "量产/突破状态": "mass_production_status",
        "证据等级": "evidence_level",
        "置信度_1到5": "confidence_score",
        "是否纳入核心池": "core_pool_flag",
        "一句话结论": "claim",
        "关键验证指标": "key_validation_metrics",
        "核心风险/反证": "counter_evidence_text",
        "Source_URL": "source_url",
        "global_anchor_links": "global_anchor_links",
        "purity_level": "purity_level",
        "ts_code": "ts_code",
        "name": "name",
        "segment": "segment",
        "sub_segment": "sub_segment",
        "product": "product",
        "source_evidence": "source_evidence",
    }

    def __init__(self, repo: Repository) -> None:
        self.repo = repo

    def import_file(self, file_path: str | Path) -> MappingImportResult:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Mapping file not found: {path}")
        raw_bytes = path.read_bytes()
        checksum = hashlib.sha256(raw_bytes).hexdigest()
        version_id = f"map_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:8]}"
        imported_at = datetime.now(UTC).replace(tzinfo=None)

        raw_df = self._read_tabular(path)
        clean_df = self._normalize(raw_df, version_id=version_id, imported_at=imported_at)
        row_count = len(clean_df)
        if row_count == 0:
            raise ValueError("No valid mapping rows found in source file.")

        self.repo.upsert_dataframe(
            "a_share_chain_mapping",
            clean_df,
            keys=["ts_code", "segment", "sub_segment"],
        )
        self.repo.upsert_dataframe(
            "a_share_chain_mapping_history",
            clean_df,
            keys=["version_id", "ts_code", "segment", "sub_segment"],
        )
        self.repo.upsert_dataframe(
            "a_share_chain_mapping_version",
            pd.DataFrame(
                [
                    {
                        "version_id": version_id,
                        "source_file": str(path),
                        "imported_at": imported_at,
                        "row_count": row_count,
                        "checksum": checksum,
                        "notes": "imported by ai-chain import mapping",
                    }
                ]
            ),
            keys=["version_id"],
        )
        return MappingImportResult(
            version_id=version_id,
            row_count=row_count,
            checksum=checksum,
            source_file=str(path),
        )

    def _read_tabular(self, path: Path) -> pd.DataFrame:
        suffix = path.suffix.lower()
        if suffix == ".csv":
            return pd.read_csv(path)
        if suffix in {".xlsx", ".xlsm", ".xls"}:
            try:
                xls = pd.ExcelFile(path)
                preferred = "A股映射主表"
                if preferred in xls.sheet_names:
                    return pd.read_excel(path, sheet_name=preferred)
                for name in xls.sheet_names:
                    if "映射" in str(name):
                        return pd.read_excel(path, sheet_name=name)
                idx = 1 if len(xls.sheet_names) > 1 else 0
                return pd.read_excel(path, sheet_name=idx)
            except ImportError as exc:
                raise RuntimeError(
                    "Reading XLSX requires openpyxl. Please install `openpyxl`."
                ) from exc
        raise ValueError(f"Unsupported file type: {suffix}")

    def _normalize(self, df: pd.DataFrame, version_id: str, imported_at: datetime) -> pd.DataFrame:
        work = df.copy()
        rename_map: dict[str, str] = {}
        for col in work.columns:
            key = str(col).strip()
            if key in self.COLUMN_ALIASES:
                rename_map[col] = self.COLUMN_ALIASES[key]
        work = work.rename(columns=rename_map)

        if "purity_level" not in work.columns:
            work["purity_level"] = work.get("mapping_type", "concept")
        if "source_evidence" not in work.columns:
            work["source_evidence"] = work.get("source_url", "")
        if "notes" not in work.columns:
            work["notes"] = work.get("claim", "")

        def _col_text(col: str, lower: bool = False) -> pd.Series:
            series = work[col] if col in work.columns else pd.Series([""] * len(work))
            out = series.astype(str).str.strip()
            return out.str.lower() if lower else out

        work["ts_code"] = _col_text("ts_code")
        work["name"] = _col_text("name")
        work["segment"] = _col_text("segment")
        work["sub_segment"] = _col_text("sub_segment")
        work["purity_level"] = _col_text("purity_level", lower=True)
        work["evidence_level"] = _col_text("evidence_level")
        work["product"] = _col_text("product")
        work["global_anchor_links"] = _col_text("global_anchor_links")
        work["source_evidence"] = _col_text("source_evidence")
        work["notes"] = _col_text("notes")
        work["source_url"] = _col_text("source_url")
        work["version_id"] = version_id
        work["is_latest"] = True
        work["last_verified_at"] = imported_at

        work["is_core"] = _col_text("core_pool_flag").str.contains("是")
        work["is_second_order"] = work["purity_level"].isin(
            {"medium", "second_order", "second-order"}
        )
        work["is_concept_only"] = work["purity_level"].isin({"concept", "low", "c"})

        work = work.replace({"nan": "", "None": "", "NaN": ""})
        work = work[
            (work["ts_code"].str.len() > 0)
            & (work["name"].str.len() > 0)
            & (work["segment"].str.len() > 0)
            & (work["sub_segment"].str.len() > 0)
        ]
        missing = sorted(c for c in self.REQUIRED_COLUMNS if c not in work.columns)
        if missing:
            raise ValueError(f"Missing required columns: {', '.join(missing)}")
        null_required = work[list(self.REQUIRED_COLUMNS)].astype(str).apply(
            lambda col: col.str.strip().eq("").any()
        )
        bad_cols = [name for name, has_empty in null_required.items() if has_empty]
        if bad_cols:
            raise ValueError(f"Required fields contain empty values: {', '.join(sorted(bad_cols))}")

        keep_cols = [
            "ts_code",
            "name",
            "segment",
            "sub_segment",
            "product",
            "global_anchor_links",
            "purity_level",
            "revenue_exposure",
            "gross_margin",
            "gross_margin_trend",
            "customer_evidence",
            "order_evidence",
            "source_evidence",
            "is_core",
            "is_second_order",
            "is_concept_only",
            "notes",
            "last_verified_at",
            "version_id",
            "is_latest",
            "evidence_level",
            "source_url",
            "claim",
            "counter_evidence_text",
            "key_validation_metrics",
            "domestic_substitution",
            "nvidia_relation",
            "mass_production_status",
            "confidence_score",
        ]
        for col in keep_cols:
            if col not in work.columns:
                work[col] = None
        return work[keep_cols].drop_duplicates(
            subset=["ts_code", "segment", "sub_segment"], keep="last"
        )
