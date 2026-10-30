"""import/export 용 CSV 스키마와 읽기/쓰기. UTF-8, 헤더 포함."""

from __future__ import annotations

import csv
import os
import tempfile
from pathlib import Path
from typing import Iterable, Iterator

from .models import Transaction, ValidationError

COLUMNS: tuple[str, ...] = ("date", "type", "category", "amount", "memo", "tags")
REQUIRED_COLUMNS: tuple[str, ...] = ("date", "type", "category", "amount")


def write_transactions(path: Path, transactions: Iterable[Transaction]) -> int:
    """임시 파일에 쓴 뒤 교체한다. 쓴 건수를 돌려준다."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        dir=path.parent, prefix=path.name + ".", suffix=".tmp"
    )
    count = 0
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(COLUMNS)
            for tx in transactions:
                writer.writerow(
                    [tx.date, tx.type, tx.category, tx.amount, tx.memo,
                     ",".join(tx.tags)]
                )
                count += 1
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
    return count


def read_rows(path: Path) -> Iterator[tuple[int, dict[str, str]]]:
    """(파일 줄 번호, 행) 을 한 행씩 yield 한다. 헤더가 잘못되면 ValidationError."""
    if not path.is_file():
        raise ValidationError(
            f"가져올 파일을 찾을 수 없습니다: {path}",
            "--from 경로를 확인하세요.",
        )
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        header = [h.strip() for h in (reader.fieldnames or [])]
        missing = [c for c in REQUIRED_COLUMNS if c not in header]
        if missing:
            raise ValidationError(
                f"CSV 헤더에 필수 컬럼이 없습니다: {', '.join(missing)}",
                f"헤더는 {','.join(COLUMNS)} 형식이어야 합니다. (memo, tags 는 선택)",
            )
        reader.fieldnames = header
        for row in reader:
            clean = {
                key: (value or "").strip()
                for key, value in row.items()
                if key is not None and isinstance(value, (str, type(None)))
            }
            yield reader.line_num, clean
