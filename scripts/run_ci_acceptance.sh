#!/usr/bin/env bash
set -euo pipefail

TARGET_DATE="${TARGET_DATE:-}"
ACCEPTANCE_DATE="${ACCEPTANCE_DATE:-}"
RUN_PIPELINE="${RUN_PIPELINE:-true}"
MAX_LOG_ROWS="${MAX_LOG_ROWS:-40}"
REVIEWER="${REVIEWER:-GitHub Actions}"
SEC_TICKERS="${SEC_TICKERS:-NVDA}"
OPENDART_SYMBOLS="${OPENDART_SYMBOLS:-005930}"
FINMIND_SYMBOLS="${FINMIND_SYMBOLS:-2330}"
FINMIND_START="${FINMIND_START:-}"
FINMIND_END="${FINMIND_END:-}"

if [[ -z "${ACCEPTANCE_DATE}" ]]; then
  ACCEPTANCE_DATE="$(date -u +%F)"
fi
if [[ -z "${TARGET_DATE}" ]]; then
  TARGET_DATE="$(date -u -d 'yesterday' +%F)"
fi
if [[ -z "${FINMIND_END}" ]]; then
  FINMIND_END="${TARGET_DATE}"
fi
if [[ -z "${FINMIND_START}" ]]; then
  FINMIND_START="$(date -u -d "${TARGET_DATE} -150 day" +%F)"
fi

echo "CI acceptance context:"
echo "  ACCEPTANCE_DATE=${ACCEPTANCE_DATE}"
echo "  TARGET_DATE=${TARGET_DATE}"
echo "  RUN_PIPELINE=${RUN_PIPELINE}"
echo "  FINMIND_START=${FINMIND_START}"
echo "  FINMIND_END=${FINMIND_END}"
echo "  SEC_TICKERS=${SEC_TICKERS}"
echo "  OPENDART_SYMBOLS=${OPENDART_SYMBOLS}"

run_nonfatal() {
  local step_name="$1"
  shift
  echo "::group::${step_name}"
  if "$@"; then
    echo "[ok] ${step_name}"
  else
    local code=$?
    echo "[warn] ${step_name} failed with exit=${code}; continue for acceptance aggregation"
  fi
  echo "::endgroup::"
}

echo "::group::init-db"
uv run ai-chain init-db
echo "::endgroup::"

if [[ "${RUN_PIPELINE}" == "true" ]]; then
  run_nonfatal "sync tushare" uv run ai-chain sync tushare --date "${TARGET_DATE}" --no-prefer-cache
  run_nonfatal "sync finmind" uv run ai-chain sync finmind \
    --start "${FINMIND_START}" --end "${FINMIND_END}" --symbols "${FINMIND_SYMBOLS}"
  run_nonfatal "sync sec" uv run ai-chain sync sec --tickers "${SEC_TICKERS}"
  run_nonfatal "sync opendart" uv run ai-chain sync opendart \
    --symbols "${OPENDART_SYMBOLS}" --date "${TARGET_DATE}"
  run_nonfatal "extract evidence" uv run ai-chain extract evidence --date "${TARGET_DATE}"
  run_nonfatal "score" uv run ai-chain score --date "${TARGET_DATE}" --intraday
  run_nonfatal "review" uv run ai-chain review --date "${TARGET_DATE}" --lookback 20
  run_nonfatal "brief" uv run ai-chain brief --date "${TARGET_DATE}" --format md
fi

echo "::group::export acceptance"
uv run ai-chain export network-acceptance \
  --date "${ACCEPTANCE_DATE}" \
  --target-date "${TARGET_DATE}" \
  --reviewer "${REVIEWER}" \
  --max-log-rows "${MAX_LOG_ROWS}"
echo "::endgroup::"

echo "Acceptance report generated: docs/NETWORK_ACCEPTANCE_${ACCEPTANCE_DATE}.md"
