from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from ai_chain_radar.db.repository import Repository
from ai_chain_radar.settings import load_yaml


def load_taxonomy(repo: Repository, config_root: str | Path = "configs") -> dict[str, int]:
    root = Path(config_root)
    segments_data = load_yaml(root / "chains" / "segments.yml").get("segments", [])
    anchors_data = load_yaml(root / "universe" / "global_anchors.yml").get("anchors", [])
    seeds_data = load_yaml(root / "universe" / "a_share_seed.yml").get("seeds", [])

    segments_df = pd.DataFrame(
        [
            {
                "segment_id": seg["id"],
                "segment_name": seg["name"],
                "parent_segment": seg.get("parent"),
                "cycle_stage": "未启动",
                "bottleneck_level": 0.0,
                "technology_generation": "",
                "upstream_segments": "",
                "downstream_segments": "",
                "key_global_anchors": ",".join(seg.get("global_anchors", [])),
                "key_a_share_symbols": "",
                "updated_at": datetime.now(UTC).replace(tzinfo=None),
            }
            for seg in segments_data
        ]
    )

    anchors_df = pd.DataFrame(
        [
            {
                "symbol": x["symbol"],
                "market": x["market"],
                "company_name": x["company_name"],
                "country": x.get("country", ""),
                "currency": x.get("currency", ""),
                "industry_layer": "",
                "chain_segment": x.get("chain_segment", ""),
                "is_core_anchor": bool(x.get("is_core_anchor", False)),
                "related_a_share_segments": "",
                "related_a_share_symbols": "",
                "source": "seed",
                "updated_at": datetime.now(UTC).replace(tzinfo=None),
            }
            for x in anchors_data
        ]
    )

    seeds_df = pd.DataFrame(
        [
            {
                "ts_code": x["ts_code"],
                "name": x["name"],
                "segment": x["segment"],
                "sub_segment": x["sub_segment"],
                "product": x["product"],
                "global_anchor_links": ",".join(x.get("global_anchor_links", [])),
                "purity_level": x.get("purity_level", "concept"),
                "is_core": bool(x.get("is_core", False)),
                "is_second_order": bool(x.get("is_second_order", False)),
                "is_concept_only": bool(x.get("is_concept_only", True)),
                "notes": "seed",
                "last_verified_at": datetime.now(UTC).replace(tzinfo=None),
            }
            for x in seeds_data
        ]
    )

    seg_written = repo.upsert_dataframe("ai_chain_segment", segments_df, keys=["segment_id"])
    anc_written = repo.upsert_dataframe(
        "global_anchor_security", anchors_df, keys=["symbol", "market"]
    )
    seed_written = repo.upsert_dataframe(
        "a_share_chain_mapping", seeds_df, keys=["ts_code", "segment", "sub_segment"]
    )
    return {"segments": seg_written, "anchors": anc_written, "a_share_seed": seed_written}
