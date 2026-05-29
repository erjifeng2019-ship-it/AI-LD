from __future__ import annotations

import gzip
import json
import re
import time
from datetime import UTC, datetime
from hashlib import sha1
from typing import Any
from urllib.request import Request, urlopen

import pandas as pd

from ai_chain_radar.db.repository import Repository
from ai_chain_radar.settings import get_settings
from ai_chain_radar.sources.base import BaseSourceAdapter, SourceRequest, SyncResult


class SecAdapter(BaseSourceAdapter):
    source_name = "sec"
    datasets = ["submissions", "companyfacts", "filings"]

    def __init__(self, repo: Repository) -> None:
        self.repo = repo
        self._min_interval_seconds = 0.12
        self._last_request_at = 0.0

    def sync(self, request: SourceRequest) -> list[SyncResult]:
        settings = get_settings()
        targets = [request.dataset] if request.dataset else self.datasets
        results: list[SyncResult] = []
        if not settings.sec_user_agent:
            for dataset in targets:
                results.append(
                    self._new_result(
                        dataset=dataset,
                        request=request,
                        status="missing_credentials",
                        error_message="Missing SEC_USER_AGENT, please configure it in .env",
                    )
                )
            return results

        tickers = request.symbols or ["NVDA", "AVGO", "MRVL", "MU"]
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
                rows = self._fetch_rows_real(dataset=dataset, tickers=tickers)
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

    def _fetch_rows_real(self, dataset: str, tickers: list[str]) -> list[dict[str, Any]]:
        user_agent = get_settings().sec_user_agent
        ticker_to_cik = self._load_ticker_cik_map(user_agent=user_agent)
        rows: list[dict[str, Any]] = []
        for ticker in tickers:
            cik = ticker_to_cik.get(ticker.upper())
            if not cik:
                continue
            if dataset == "companyfacts":
                payload = self._get_json(
                    f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json",
                    user_agent=user_agent,
                )
                rows.extend(
                    self._extract_companyfacts_rows(ticker=ticker, cik=cik, payload=payload)
                )
                continue

            submissions = self._get_json(
                f"https://data.sec.gov/submissions/CIK{cik:010d}.json",
                user_agent=user_agent,
            )
            rows.extend(self._extract_submission_rows(ticker=ticker, cik=cik, payload=submissions))
        return rows

    def _extract_submission_rows(
        self, ticker: str, cik: int, payload: dict[str, Any]
    ) -> list[dict[str, Any]]:
        recent = payload.get("filings", {}).get("recent", {})
        forms = recent.get("form", [])
        accession_numbers = recent.get("accessionNumber", [])
        filing_dates = recent.get("filingDate", [])
        report_dates = recent.get("reportDate", [])
        primary_docs = recent.get("primaryDocument", [])

        rows: list[dict[str, Any]] = []
        for idx, form in enumerate(forms):
            if form not in {"10-K", "10-Q", "8-K"}:
                continue
            accession = accession_numbers[idx] if idx < len(accession_numbers) else ""
            filing_date = filing_dates[idx] if idx < len(filing_dates) else ""
            report_date = report_dates[idx] if idx < len(report_dates) else ""
            primary_doc = primary_docs[idx] if idx < len(primary_docs) else ""
            filing_url = (
                "https://www.sec.gov/Archives/edgar/data/"
                f"{cik}/{accession.replace('-', '')}/{primary_doc}"
            )
            keywords = self._extract_keywords([str(form), str(primary_doc)])
            rows.append(
                {
                    "accession_number": accession or f"{ticker}-{idx}",
                    "cik": str(cik),
                    "symbol": ticker,
                    "company_name": payload.get("name", ticker),
                    "form_type": form,
                    "filing_date": filing_date,
                    "report_date": report_date,
                    "filing_url": filing_url,
                    "keywords_json": json.dumps(keywords, ensure_ascii=False),
                    "impact_segments": self._map_segments_from_keywords(keywords),
                }
            )
        return rows

    def _extract_companyfacts_rows(
        self, ticker: str, cik: int, payload: dict[str, Any]
    ) -> list[dict[str, Any]]:
        company_name = str(payload.get("entityName", ticker))
        us_gaap = payload.get("facts", {}).get("us-gaap", {})
        if not isinstance(us_gaap, dict):
            return []
        watched_metrics = {
            "RevenueFromContractWithCustomerExcludingAssessedTax": "revenue",
            "Revenues": "revenues",
            "NetIncomeLoss": "net_income",
            "ResearchAndDevelopmentExpense": "rd_expense",
        }

        rows: list[dict[str, Any]] = []
        for xbrl_tag, metric_name in watched_metrics.items():
            metric_payload = us_gaap.get(xbrl_tag)
            if not isinstance(metric_payload, dict):
                continue
            units = metric_payload.get("units")
            if not isinstance(units, dict) or not units:
                continue
            unit_name, entries = self._pick_unit_entries(units)
            if not unit_name:
                continue
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                period_end = str(entry.get("end", "")).strip()
                if not period_end:
                    continue
                value = entry.get("val")
                if value in (None, ""):
                    continue
                form_type = str(entry.get("form", "")).strip()
                fiscal_year = str(entry.get("fy", "")).strip()
                fiscal_period = str(entry.get("fp", "")).strip()
                filed_date = str(entry.get("filed", "")).strip()
                fact_id = self._stable_id(
                    str(cik),
                    xbrl_tag,
                    period_end,
                    form_type,
                    fiscal_year,
                    fiscal_period,
                    str(value),
                )
                rows.append(
                    {
                        "fact_id": fact_id,
                        "cik": str(cik),
                        "symbol": ticker,
                        "company_name": company_name,
                        "metric_name": metric_name,
                        "xbrl_tag": xbrl_tag,
                        "unit": unit_name,
                        "period_end": period_end,
                        "filed_date": filed_date,
                        "fiscal_year": fiscal_year,
                        "fiscal_period": fiscal_period,
                        "form_type": form_type,
                        "value": self._to_float(value),
                        "source": "sec",
                    }
                )
        return rows

    def _pick_unit_entries(self, units: dict[str, Any]) -> tuple[str, list[Any]]:
        preferred = units.get("USD")
        if isinstance(preferred, list):
            return "USD", preferred
        for unit_name, entries in units.items():
            if isinstance(entries, list):
                return str(unit_name), entries
        return "", []

    def _normalize_and_write(self, dataset: str, rows: list[dict[str, Any]]) -> int:
        if not rows:
            return 0
        frame = pd.DataFrame(rows)
        if dataset == "companyfacts":
            frame["period_end"] = frame["period_end"].apply(
                lambda value: self._normalize_date(value, "1970-01-01")
            )
            frame["filed_date"] = frame["filed_date"].apply(
                lambda value: self._normalize_date(value, "1970-01-01")
            )
            frame["ingested_at"] = datetime.now(UTC).replace(tzinfo=None)
            return self.repo.upsert_dataframe("us_sec_company_fact", frame, keys=["fact_id"])

        frame["raw_path"] = ""
        frame["extracted_text_path"] = ""
        frame["key_items_json"] = frame["keywords_json"]
        frame["sentiment_score"] = 60.0
        frame["ingested_at"] = datetime.now(UTC).replace(tzinfo=None)
        return self.repo.upsert_dataframe("us_sec_filing_event", frame, keys=["accession_number"])

    def _load_ticker_cik_map(self, user_agent: str) -> dict[str, int]:
        payload = self._get_json(
            "https://www.sec.gov/files/company_tickers.json", user_agent=user_agent
        )
        mapping: dict[str, int] = {}
        if isinstance(payload, dict):
            for value in payload.values():
                if not isinstance(value, dict):
                    continue
                ticker = str(value.get("ticker", "")).upper()
                cik = value.get("cik_str")
                if ticker and isinstance(cik, int):
                    mapping[ticker] = cik
        return mapping

    def _get_json(self, url: str, user_agent: str) -> dict[str, Any]:
        now = time.monotonic()
        elapsed = now - self._last_request_at
        if elapsed < self._min_interval_seconds:
            time.sleep(self._min_interval_seconds - elapsed)
        req = Request(
            url=url,
            headers={"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"},
            method="GET",
        )
        with urlopen(req, timeout=20) as resp:  # noqa: S310
            body = resp.read()
            encoding = (resp.headers.get("Content-Encoding") or "").lower()
            if "gzip" in encoding:
                body = gzip.decompress(body)
            payload = json.loads(body.decode("utf-8"))
        self._last_request_at = time.monotonic()
        return payload

    def _extract_keywords(self, texts: list[str]) -> list[str]:
        joined = " ".join(texts).lower()
        candidates = ["hbm", "cpo", "data center", "advanced packaging", "silicon photonics"]
        return [word for word in candidates if re.search(re.escape(word), joined)]

    def _map_segments_from_keywords(self, keywords: list[str]) -> str:
        segments: list[str] = []
        for word in keywords:
            if word == "hbm":
                segments.append("hbm_storage")
            if word in {"cpo", "silicon photonics"}:
                segments.append("optics_cpo_16t")
            if word == "advanced packaging":
                segments.append("cowos_advanced_packaging")
            if word == "data center":
                segments.append("liquid_cooling_power")
        uniq = sorted(set(segments))
        return ",".join(uniq)

    def _normalize_date(self, value: Any, fallback: str) -> str:
        text = str(value or fallback).strip()
        if len(text) == 8 and text.isdigit():
            return f"{text[0:4]}-{text[4:6]}-{text[6:8]}"
        return text

    def _to_float(self, value: Any) -> float | None:
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return None
            try:
                return float(text)
            except ValueError:
                return None
        return None

    def _stable_id(self, *parts: str) -> str:
        token = "|".join(part.strip() for part in parts)
        return sha1(token.encode("utf-8")).hexdigest()
