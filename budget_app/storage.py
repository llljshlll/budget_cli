"""JSONL 파일 저장소. 파일 I/O 와 스트리밍만 담당하고 비즈니스 규칙은 모른다."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Callable, Generic, Iterable, Iterator, TypeVar

from .models import (
    Budget,
    BudgetAppError,
    DuplicateError,
    NotFoundError,
    StorageError,
    Transaction,
    format_tx_id,
    tx_number,
)

T = TypeVar("T")

DEFAULT_CATEGORIES: tuple[str, ...] = (
    "food", "transport", "rent", "salary", "etc",
)


def _dumps(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


class JsonlFile(Generic[T]):
    """한 줄 = 한 레코드인 JSONL 파일."""

    def __init__(
        self,
        path: Path,
        encode: Callable[[T], dict[str, Any]],
        decode: Callable[[dict[str, Any]], T],
    ) -> None:
        self.path = path
        self._encode = encode
        self._decode = decode

    def stream(self) -> Iterator[T]:
        """파일을 한 줄씩 읽어 yield 한다. 전체를 메모리에 올리지 않는다."""
        if not self.path.exists():
            return
        with self.path.open("r", encoding="utf-8") as handle:
            for line_no, line in enumerate(handle, start=1):
                text = line.strip()
                if not text:
                    continue
                try:
                    item = self._decode(json.loads(text))
                except (
                    ValueError, KeyError, TypeError, AttributeError, BudgetAppError
                ) as exc:
                    raise StorageError(
                        f"{self.path.name} {line_no}번째 줄을 읽을 수 없습니다.",
                        "파일이 손상되었습니다. 해당 줄을 수정하거나 삭제한 뒤 다시 실행하세요.",
                    ) from exc
                yield item

    def append(self, item: T) -> None:
        self.append_many([item])

    def append_many(self, items: Iterable[T]) -> None:
        payload = "".join(_dumps(self._encode(i)) + "\n" for i in items)
        if not payload:
            return
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())

    def rewrite(self, items: Iterable[T]) -> None:
        """임시 파일에 쓴 뒤 os.replace 로 교체한다. 실패하면 원본은 그대로 남는다."""
        fd, tmp_name = tempfile.mkstemp(
            dir=self.path.parent, prefix=self.path.name + ".", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                for item in items:
                    handle.write(_dumps(self._encode(item)) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, self.path)
        except BaseException:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise

    def ensure(self) -> bool:
        """파일이 없으면 만들고 True 를 돌려준다."""
        if self.path.exists():
            return False
        self.path.touch()
        return True


class TransactionRepository(JsonlFile[Transaction]):
    def __init__(self, path: Path) -> None:
        super().__init__(path, Transaction.to_dict, Transaction.from_dict)

    def stream_all(self) -> Iterator[Transaction]:
        return self.stream()

    def next_id(self) -> str:
        highest = max((tx_number(tx.id) for tx in self.stream()), default=0)
        return format_tx_id(highest + 1)

    def next_ids(self, count: int) -> list[str]:
        highest = max((tx_number(tx.id) for tx in self.stream()), default=0)
        return [format_tx_id(highest + i) for i in range(1, count + 1)]

    def get(self, tx_id: str) -> Transaction | None:
        return next((tx for tx in self.stream() if tx.id == tx_id), None)

    def update(self, tx_id: str, new_tx: Transaction) -> None:
        if self.get(tx_id) is None:
            raise NotFoundError(
                f"존재하지 않는 거래 id 입니다: {tx_id}",
                "list 명령으로 id 를 확인하세요.",
            )
        self.rewrite(new_tx if tx.id == tx_id else tx for tx in self.stream())

    def delete(self, tx_id: str) -> None:
        if self.get(tx_id) is None:
            raise NotFoundError(
                f"존재하지 않는 거래 id 입니다: {tx_id}",
                "list 명령으로 id 를 확인하세요.",
            )
        self.rewrite(tx for tx in self.stream() if tx.id != tx_id)

    def count_by_category(self, name: str) -> int:
        return sum(1 for tx in self.stream() if tx.category == name)


class CategoryStore:
    def __init__(self, path: Path) -> None:
        self._file: JsonlFile[str] = JsonlFile(
            path, lambda n: {"name": n}, lambda d: str(d["name"])
        )

    @property
    def path(self) -> Path:
        return self._file.path

    def list(self) -> list[str]:
        return sorted(self._file.stream())

    def exists(self, name: str) -> bool:
        return any(n == name for n in self._file.stream())

    def add(self, name: str) -> None:
        if self.exists(name):
            raise DuplicateError(
                f"이미 등록된 카테고리입니다: {name}",
                "category list 로 등록된 카테고리를 확인하세요.",
            )
        self._file.append(name)

    def remove(self, name: str) -> None:
        if not self.exists(name):
            raise NotFoundError(
                f"등록되지 않은 카테고리입니다: {name}",
                "category list 로 등록된 카테고리를 확인하세요.",
            )
        self._file.rewrite(n for n in self._file.stream() if n != name)

    def ensure_defaults(self) -> bool:
        """비어 있으면 기본 카테고리를 채우고 True 를 돌려준다."""
        if any(True for _ in self._file.stream()):
            return False
        self._file.append_many(DEFAULT_CATEGORIES)
        return True

    def ensure_file(self) -> bool:
        return self._file.ensure()


class BudgetStore:
    def __init__(self, path: Path) -> None:
        self._file: JsonlFile[Budget] = JsonlFile(
            path, Budget.to_dict, Budget.from_dict
        )

    @property
    def path(self) -> Path:
        return self._file.path

    def get(self, month: str) -> Budget | None:
        return next((b for b in self._file.stream() if b.month == month), None)

    def set(self, budget: Budget) -> None:
        items = [b for b in self._file.stream() if b.month != budget.month]
        items.append(budget)
        items.sort(key=lambda b: b.month)
        self._file.rewrite(items)

    def ensure_file(self) -> bool:
        return self._file.ensure()


class Storage:
    """data 폴더 안의 저장 파일 3개를 묶는다."""

    def __init__(self, data_dir: str | Path) -> None:
        self.data_dir = Path(data_dir)
        self.transactions = TransactionRepository(
            self.data_dir / "transactions.jsonl"
        )
        self.categories = CategoryStore(self.data_dir / "categories.jsonl")
        self.budgets = BudgetStore(self.data_dir / "budgets.jsonl")

    def initialize(self) -> list[str]:
        """폴더와 파일이 없으면 만들고, 사용자에게 알릴 안내 메시지를 돌려준다."""
        notices: list[str] = []
        if not self.data_dir.exists():
            self.data_dir.mkdir(parents=True)
            notices.append(f"[초기화] 데이터 폴더를 만들었습니다: {self.data_dir}")
        elif not self.data_dir.is_dir():
            raise StorageError(
                f"데이터 경로가 폴더가 아닙니다: {self.data_dir}",
                "--data-dir 로 폴더 경로를 지정하세요.",
            )
        created = [
            self.transactions.ensure(),
            self.categories.ensure_file(),
            self.budgets.ensure_file(),
        ]
        if any(created) and not notices:
            notices.append("[초기화] 없는 저장 파일을 새로 만들었습니다.")
        if self.categories.ensure_defaults():
            names = ", ".join(DEFAULT_CATEGORIES)
            notices.append(f"[초기화] 기본 카테고리를 만들었습니다: {names}")
        return notices
