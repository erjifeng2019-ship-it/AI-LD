from __future__ import annotations

from pathlib import Path

import pandas as pd

from ai_chain_radar.db.repository import Repository
from ai_chain_radar.importers.mapping_importer import MappingImporter


def test_mapping_importer_csv(tmp_path: Path) -> None:
    repo = Repository()
    repo.init_db()

    file_path = tmp_path / "mapping.csv"
    pd.DataFrame(
        [
            {
                "ts_code": "300308.SZ",
                "name": "中际旭创",
                "segment": "optics_cpo_16t",
                "sub_segment": "光模块",
                "product": "800G/1.6T",
                "purity_level": "high",
                "evidence_level": "A1",
                "source_evidence": "https://example.com/1",
            },
            {
                "ts_code": "688008.SH",
                "name": "澜起科技",
                "segment": "optics_cpo_16t",
                "sub_segment": "互连芯片",
                "product": "Retimer",
                "purity_level": "medium",
                "evidence_level": "A1",
                "source_evidence": "https://example.com/2",
            },
        ]
    ).to_csv(file_path, index=False)

    result = MappingImporter(repo).import_file(file_path)
    assert result.row_count == 2
    assert result.version_id.startswith("map_")

    main_cnt = repo.query_dataframe("SELECT count(*) AS cnt FROM a_share_chain_mapping")
    assert int(main_cnt.iloc[0]["cnt"]) >= 2

    version_cnt = repo.query_dataframe("SELECT count(*) AS cnt FROM a_share_chain_mapping_version")
    assert int(version_cnt.iloc[0]["cnt"]) == 1

    history_cnt = repo.query_dataframe("SELECT count(*) AS cnt FROM a_share_chain_mapping_history")
    assert int(history_cnt.iloc[0]["cnt"]) == 2

