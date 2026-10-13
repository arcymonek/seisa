from datetime import date

from backend.logging_config import prune_old_logs


def test_prune_keeps_thirty_days_including_today(tmp_path):
    today = date(2026, 10, 13)
    # 30 days = 2026-09-14 (oldest kept) .. 2026-10-13 (today)
    for name in ["2026-09-13", "2026-09-14", "2026-10-13", "2026-01-01"]:
        (tmp_path / f"{name}.jsonl").write_text("{}\n")
    prune_old_logs(tmp_path, today)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["2026-09-14.jsonl", "2026-10-13.jsonl"]


def test_prune_ignores_other_files(tmp_path):
    (tmp_path / "launcher.log").write_text("x")
    (tmp_path / "notes.jsonl").write_text("x")
    (tmp_path / ".gitkeep").write_text("")
    prune_old_logs(tmp_path, date(2026, 10, 13))
    assert len(list(tmp_path.iterdir())) == 3


def test_prune_missing_directory_is_harmless(tmp_path):
    prune_old_logs(tmp_path / "nope", date(2026, 10, 13))
