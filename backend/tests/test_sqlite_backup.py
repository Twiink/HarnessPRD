"""在线 WAL 备份与恢复使用 SQLite API，目标发布不可覆盖。"""

from pathlib import Path
import sqlite3
import subprocess
import sys


SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "sqlite-backup.py"


def run_copy(operation, source, target):
    return subprocess.run(
        [sys.executable, str(SCRIPT), operation, str(source), str(target)],
        capture_output=True,
        text=True,
        timeout=10,
    )


def test_online_wal_backup_restore_and_no_overwrite(tmp_path):
    source, backup, restored = (tmp_path / name for name in ("live.db", "backup.db", "restored.db"))
    conn = sqlite3.connect(source)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("CREATE TABLE sample(value TEXT)")
        conn.execute("INSERT INTO sample VALUES ('committed')")
        conn.commit()
        assert source.with_suffix(".db-wal").exists()
        result = run_copy("backup", source, backup)
        assert result.returncode == 0, result.stderr
        conn.execute("INSERT INTO sample VALUES ('later')")
        conn.commit()
        result = run_copy("restore", backup, restored)
        assert result.returncode == 0, result.stderr
        with sqlite3.connect(restored) as recovered:
            assert recovered.execute("SELECT * FROM sample").fetchall() == [("committed",)]
        before = restored.read_bytes()
        assert run_copy("restore", backup, restored).returncode == 1
        assert restored.read_bytes() == before
    finally:
        conn.close()


def test_invalid_backup_does_not_publish_target(tmp_path):
    source, target = tmp_path / "corrupt.db", tmp_path / "new.db"
    source.write_text("not a database")
    assert run_copy("restore", source, target).returncode == 1
    assert not target.exists()
    assert not list(tmp_path.glob(".sqlite-copy-*"))
