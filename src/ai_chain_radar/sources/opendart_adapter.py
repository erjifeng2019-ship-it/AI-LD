from __future__ import annotations

import io
import json
import zipfile
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

import pandas as pd

from ai_chain_radar.db.repository import Repository
from ai_chain_radar.settings import get_settings
from ai_chain_radar.sources.base import BaseSourceAdapter, SourceRequest, SyncResult


class OpenDartAdapter(BaseSourceAdapter):
    source_name = "opendart"
    datasets = ["corp_code", "disclosures"]

    def __init__(self, repo: Repository) -> None:
        self.repo = repo

    def sync(self, request: SourceRequest) -> list[SyncResult]:
        settings = get_settings()
        targets = [request.dataset] if request.dataset else self.datasets
        results: list[SyncResult] = []
        if not settings.opendart_api_key:
            for dataset in targets:
                results.append(
                    self._new_result(
                        dataset=dataset,
                        request=request,
                        status="missing_credentials",
                        error_message="Missing OPENDART_API_KEY, please configure it in .env",
                    )
                )
            return results

        symbols = request.symbols or ["005930", "000660"]
        for dataset in targets:
            if request.dry_run:
                results.append(
                    self._new_result(
                        dataset=dataset,
                        request=request,
                        status="skipped",
                        rows_read=0,
                        rows_written=0,
                        error_message="dry-run enabled, skipped network fetch",
                    )
                )
                continue
            started_at = datetime.now(UTC).replace(tzinfo=None)
            try:
                rows = self._fetch_rows_real(dataset=dataset, symbols=symbols, request=request)
                raw_path = self._save_raw_jsonl(dataset, request.date or "latest", rows)
                written = self._normalize_and_write(dataset=dataset, rows=rows)
                results.append(
                    self._new_result(
                        dataset=dataset,
                        request=request,
                        status="ok" if written > 0 else "empty",
                        rows_read=len(rows),
                        rows_written=written,
                        raw_path=raw_path,
                        started_at=started_at,
                    )
                )
            except Exception as exc:
                results.append(
                    self._new_result(
                        dataset=dataset,
                        request=request,
                        status="failed",
                        error_message=str(exc),
                        started_at=started_at,
                    )
                )
        return results

    def _fetch_rows_real(
        self, dataset: str, symbols: list[str], request: SourceRequest
    ) -> list[dict[str, Any]]:
        api_key = get_settings().opendart_api_key
        corp_master_rows = self._load_corp_master(api_key=api_key)
        if dataset == "corp_code":
            symbols_upper = {symbol.strip() for symbol in symbols}
            return [
                row
                for row in corp_master_rows
                if row.get("stock_code") and row["stock_code"] in symbols_upper
            ]

        corp_code_map = {
            row["stock_code"]: row["corp_code"]
            for row in corp_master_rows
            if row.get("stock_code") and row.get("corp_code")
        }
        bgn_de = (request.start or request.date or "2026-01-01").replace("-", "")
        end_de = (request.end or request.date or "2026-05-28").replace("-", "")
        rows: list[dict[str, Any]] = []
        for symbol in symbols:
            corp_code = corp_code_map.get(symbol)
            if not corp_code:
                continue
            query = {
                "crtfc_key": api_key,
                "corp_code": corp_code,
                "bgn_de": bgn_de,
                "end_de": end_de,
                "page_no": "1",
                "page_count": "20",
            }
            url = "https://opendart.fss.or.kr/api/list.json?" + urlencode(query)
            payload = self._get_json(url)
            items = payload.get("list", [])
            if not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, dict):
                    continue
                rows.append(
                    {
                        "rcept_no": item.get("rcept_no", f"{symbol}-{len(rows)}"),
                        "corp_code": corp_code,
                        "stock_code": symbol,
                        "corp_name": item.get("corp_name", symbol),
                        "report_nm": item.get("report_nm", ""),
                        "rcept_dt": item.get("rcept_dt", ""),
                        "rm": item.get("rm", ""),
                        "raw_url": "https://opendart.fss.or.kr",
                        "impact_segments": self._infer_segment(item.get("report_nm", "")),
                    }
                )
        return rows

    def _load_corp_master(self, api_key: str) -> list[dict[str, str]]:
        url = f"https://opendart.fss.or.kr/api/corpCode.xml?crtfc_key={api_key}"
        req = Request(url=url, method="GET")
        with urlopen(req, timeout=30) as resp:  # noqa: S310
            binary = resp.read()
        with zipfile.ZipFile(io.BytesIO(binary)) as zf:
            xml_name = zf.namelist()[0]
            with zf.open(xml_name) as raw_xml:
                root = ET.parse(raw_xml).getroot()
        rows: list[dict[str, str]] = []
        for node in root.findall("list"):
            stock_code = (node.findtext("stock_code") or "").strip()
            corp_code = (node.findtext("corp_code") or "").strip()
            corp_name = (node.findtext("corp_name") or "").strip()
            modify_date = (node.findtext("modify_date") or "").strip()
            if corp_code:
                rows.append(
                    {
                        "corp_code": corp_code,
                        "stock_code": stock_code,
                        "corp_name": corp_name,
                        "modify_date": modify_date,
                    }
                )
        return rows

    def _get_json(self, url: str) -> dict[str, Any]:
        req = Request(url=url, method="GET")
        with urlopen(req, timeout=20) as resp:  # noqa: S310
            return json.loads(resp.read().decode("utf-8"))

    def _infer_segment(self, report_name: str) -> str:
        name = report_name.lower()
        if "semiconductor" in name:
            return "hbm_storage"
        return "hbm_storage"

    def _normalize_and_write(self, dataset: str, rows: list[dict[str, Any]]) -> int:
        if not rows:
            return 0
        frame = pd.DataFrame(rows)
        frame["source"] = "opendart"
        frame["ingested_at"] = datetime.now(UTC).replace(tzinfo=None)
        if dataset == "corp_code":
            return self.repo.upsert_dataframe("korea_corp_code_master", frame, keys=["corp_code"])

        frame["raw_path"] = ""
        frame["key_items_json"] = '["HBM","capacity constrained"]'
        return self.repo.upsert_dataframe("korea_disclosure_event", frame, keys=["rcept_no"])
