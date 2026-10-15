#!/usr/bin/env python3
"""通过 SQLite backup API 创建一致副本；备份与恢复均拒绝覆盖目标。"""

import argparse
from contextlib import closing
import os
from pathlib import Path
import sqlite3
import tempfile
import time


def copy_database(source: Path, target: Path, timeout: float = 30) -> None:
    source = source.resolve(strict=True)
    target = target.absolute()
    if target.exists() or target.is_symlink():
        raise FileExistsError("目标已存在，请选择新的数据库路径")
    target.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout

    def progress(status: int, remaining: int, total: int) -> None:
        if time.monotonic() > deadline:
            raise TimeoutError("数据库复制超时")

    descriptor, temporary = tempfile.mkstemp(prefix=".sqlite-copy-", dir=target.parent)
    os.close(descriptor)
    try:
        with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as origin:
            destination = sqlite3.connect(temporary)
            try:
                origin.backup(destination, pages=256, progress=progress, sleep=0.05)
                if destination.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                    raise ValueError("数据库完整性校验失败")
            finally:
                destination.close()
        # 同目录硬链接原子发布，目标被其他进程创建时也不会覆盖。
        os.link(temporary, target)
    finally:
        Path(temporary).unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("backup", "restore"))
    parser.add_argument("source", type=Path)
    parser.add_argument("target", type=Path)
    parser.add_argument("--timeout", type=float, default=30)
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("timeout 必须大于 0")
    try:
        copy_database(args.source, args.target, args.timeout)
    except (OSError, sqlite3.Error, ValueError, TimeoutError) as exc:
        parser.exit(1, f"复制失败：{exc}\n")
    print(f"{args.operation} 完成，完整性校验通过：{args.target}")


if __name__ == "__main__":
    main()
