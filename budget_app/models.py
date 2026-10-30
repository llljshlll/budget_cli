"""데이터 구조, 입력 검증, 예외 계층. 파일 I/O는 하지 않는다."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date as _date
from typing import Any, Literal, get_args

TxType = Literal["income", "expense"]
TX_TYPES: tuple[str, ...] = get_args(TxType)

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
_INT_RE = re.compile(r"^[+-]?\d+$")


# ---------------------------------------------------------------- 예외 계층
class BudgetAppError(Exception):
    """모든 앱 예외의 기반. 원인(message)과 해결 힌트(hint)를 함께 가진다."""

    exit_code = 1

    def __init__(self, message: str, hint: str = "") -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint


class ValidationError(BudgetAppError):
    """입력값이 규칙에 맞지 않을 때."""


class NotFoundError(BudgetAppError):
    """없는 id, 없는 카테고리 등 대상을 찾지 못했을 때."""


class DuplicateError(BudgetAppError):
    """이미 존재하는 항목을 또 추가하려 할 때."""


class CategoryInUseError(BudgetAppError):
    """거래가 사용 중인 카테고리를 삭제하려 할 때."""


class StorageError(BudgetAppError):
    """저장 파일을 읽거나 쓸 수 없을 때."""

    exit_code = 2


# ---------------------------------------------------------------- 검증 함수
def parse_date(value: str) -> str:
    text = value.strip()
    if _DATE_RE.match(text):
        try:
            _date.fromisoformat(text)
            return text
        except ValueError:
            pass
    raise ValidationError(
        "날짜 형식이 올바르지 않습니다 (YYYY-MM-DD).", "예: 2024-01-15"
    )


def parse_month(value: str) -> str:
    text = value.strip()
    if not _MONTH_RE.match(text):
        raise ValidationError(
            "월 형식이 올바르지 않습니다 (YYYY-MM).", "예: 2024-01"
        )
    return text


def parse_amount(value: str | int) -> int:
    if isinstance(value, bool):
        raise ValidationError("금액은 정수여야 합니다.", "예: 15000")
    if isinstance(value, int):
        number = value
    else:
        text = value.strip()
        if not _INT_RE.match(text):
            raise ValidationError(
                "금액은 정수여야 합니다.", "숫자만 입력하세요. 예: 15000"
            )
        number = int(text)
    if number <= 0:
        raise ValidationError(
            "금액은 0보다 큰 양수여야 합니다.", "예: 15000"
        )
    return number


def parse_type(value: str) -> TxType:
    text = value.strip().lower()
    if text == "income":
        return "income"
    if text == "expense":
        return "expense"
    raise ValidationError(
        "타입은 income 또는 expense 만 사용할 수 있습니다.",
        "수입이면 income, 지출이면 expense 를 입력하세요.",
    )


def parse_tags(value: str) -> tuple[str, ...]:
    return tuple(t for t in (p.strip() for p in value.split(",")) if t)


def parse_category_name(value: str) -> str:
    name = value.strip()
    if not name:
        raise ValidationError("카테고리명이 비어 있습니다.", "예: food")
    return name


def tx_number(tx_id: str) -> int:
    """'TX-000012' -> 12. 형식이 다르면 0."""
    prefix, _, digits = tx_id.partition("-")
    if prefix == "TX" and digits.isdigit():
        return int(digits)
    return 0


def format_tx_id(number: int) -> str:
    return f"TX-{number:06d}"


# ---------------------------------------------------------------- 데이터 모델
@dataclass(frozen=True)
class Transaction:
    id: str
    type: TxType
    date: str
    amount: int
    category: str
    memo: str = ""
    tags: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "date": self.date,
            "amount": self.amount,
            "category": self.category,
            "memo": self.memo,
            "tags": list(self.tags),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Transaction:
        return cls(
            id=str(data["id"]),
            type=parse_type(str(data["type"])),
            date=parse_date(str(data["date"])),
            amount=parse_amount(data["amount"]),
            category=str(data["category"]),
            memo=str(data.get("memo", "")),
            tags=tuple(str(t) for t in data.get("tags", [])),
        )


@dataclass(frozen=True)
class Budget:
    month: str
    amount: int

    def to_dict(self) -> dict[str, Any]:
        return {"month": self.month, "amount": self.amount}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Budget:
        return cls(
            month=parse_month(str(data["month"])),
            amount=parse_amount(data["amount"]),
        )


@dataclass(frozen=True)
class SearchCriteria:
    """search 조건. None 인 항목은 조건 없음."""

    date_from: str | None = None
    date_to: str | None = None
    category: str | None = None
    type: TxType | None = None
    q: str | None = None
    tag: str | None = None

    def matches(self, tx: Transaction) -> bool:
        if self.date_from is not None and tx.date < self.date_from:
            return False
        if self.date_to is not None and tx.date > self.date_to:
            return False
        if self.category is not None and tx.category != self.category:
            return False
        if self.type is not None and tx.type != self.type:
            return False
        if self.q is not None and self.q.lower() not in tx.memo.lower():
            return False
        if self.tag is not None and self.tag.lower() not in (
            t.lower() for t in tx.tags
        ):
            return False
        return True


@dataclass(frozen=True)
class MonthlySummary:
    month: str
    tx_count: int
    total_income: int
    total_expense: int
    balance: int
    top_expenses: tuple[tuple[str, int], ...]
    budget: Budget | None
    usage_percent: float | None
    over_budget: bool


@dataclass(frozen=True)
class ImportResult:
    imported: int
    skipped: int
    errors: tuple[str, ...] = ()
