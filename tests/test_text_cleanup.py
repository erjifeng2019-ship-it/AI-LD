from __future__ import annotations

from ai_chain_radar.db.repository import Repository
from ai_chain_radar.reports.text_cleanup import cleanup_mojibake_text


def test_text_cleanup_preview_and_apply(monkeypatch) -> None:
    repo = Repository()
    repo.init_db()
    repo.query_dataframe(
        """
        INSERT INTO a_share_announcement_event (
          ann_id, ann_date, ts_code, name, title, source, ingested_at
        ) VALUES (
          'ann_test_1', '2026-05-28', '300308.SZ',
          'raw_name', 'raw_title', 'test', now()
        )
        """
    )

    def _fake_normalize(value: str) -> str:
        text = str(value)
        if text == "raw_name":
            return "fixed_name"
        if text == "raw_title":
            return "fixed_title"
        return text

    monkeypatch.setattr("ai_chain_radar.reports.text_cleanup.normalize_text", _fake_normalize)

    preview = cleanup_mojibake_text(repo=repo, apply_changes=False)
    changed = {item.table: item.changed_rows for item in preview}
    assert changed.get("a_share_announcement_event", 0) >= 1

    before = repo.query_dataframe(
        """
        SELECT name, title
        FROM a_share_announcement_event
        WHERE ann_id = 'ann_test_1'
        """
    ).iloc[0]
    assert str(before["name"]) == "raw_name"

    cleanup_mojibake_text(repo=repo, apply_changes=True)
    after = repo.query_dataframe(
        """
        SELECT name, title
        FROM a_share_announcement_event
        WHERE ann_id = 'ann_test_1'
        """
    ).iloc[0]
    assert str(after["name"]) == "fixed_name"
    assert str(after["title"]) == "fixed_title"
