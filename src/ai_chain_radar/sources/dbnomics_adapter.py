from __future__ import annotations

from ai_chain_radar.sources.base import BaseSourceAdapter, SourceRequest, SyncResult


class DBnomicsAdapter(BaseSourceAdapter):
    source_name = "dbnomics"

    def sync(self, request: SourceRequest) -> list[SyncResult]:
        return [
            self._new_result(
                dataset=request.dataset or "default",
                request=request,
                status="skipped",
                error_message="DBnomics adapter is scaffolded but not implemented in MVP.",
            )
        ]
