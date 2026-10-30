"""비즈니스 규칙: 검증, 카테고리 확인, 요약 집계, CSV 입출력 흐름."""

from __future__ import annotations

import heapq
from collections import Counter
from dataclasses import replace
from pathlib import Path
from typing import Any, Iterator

from . import csv_io
from .decorators import log_call, timed
from .models import (
    Budget,
    CategoryInUseError,
    ImportResult,
    MonthlySummary,
    NotFoundError,
    SearchCriteria,
    Transaction,
    ValidationError,
    parse_amount,
    parse_category_name,
    parse_date,
    parse_month,
    parse_tags,
    parse_type,
)
from .storage import BudgetStore, CategoryStore, Storage, TransactionRepository


def _sort_key(tx: Transaction) -> tuple[str, str]:
    return (tx.date, tx.id)


class CategoryService:
    def __init__(self, categories: CategoryStore, repo: TransactionRepository) -> None:
        self._categories = categories
        self._repo = repo

    def list(self) -> list[str]:
        return self._categories.list()

    def require(self, name: str) -> str:
        """등록된 카테고리인지 확인하고 정규화된 이름을 돌려준다."""
        clean = parse_category_name(name)
        if not self._categories.exists(clean):
            registered = ", ".join(self._categories.list()) or "(없음)"
            raise NotFoundError(
                f"등록되지 않은 카테고리입니다: {clean}",
                f"등록된 카테고리: {registered} / 새로 등록: category add --name {clean}",
            )
        return clean

    @log_call
    def add(self, name: str) -> str:
        clean = parse_category_name(name)
        self._categories.add(clean)
        return clean

    @log_call
    def remove(self, name: str) -> str:
        clean = parse_category_name(name)
        if not self._categories.exists(clean):
            self._categories.remove(clean)  # NotFoundError 발생
        used = self._repo.count_by_category(clean)
        if used:
            raise CategoryInUseError(
                f"'{clean}' 카테고리를 사용하는 거래가 {used}건 있어 삭제할 수 없습니다.",
                "해당 거래를 update --category 로 다른 카테고리로 바꾸거나 delete 한 뒤 다시 시도하세요.",
            )
        self._categories.remove(clean)
        return clean


class TransactionService:
    def __init__(self, repo: TransactionRepository, categories: CategoryService) -> None:
        self._repo = repo
        self._categories = categories

    @log_call
    def add(self, *, date: str, type: str, category: str, amount: str | int,
            memo: str = "", tags: str = "") -> Transaction:
        tx = Transaction(
            id=self._repo.next_id(),
            type=parse_type(type),
            date=parse_date(date),
            amount=parse_amount(amount),
            category=self._categories.require(category),
            memo=memo.strip(),
            tags=parse_tags(tags),
        )
        self._repo.append(tx)
        return tx

    @log_call
    def update(self, tx_id: str, *, date: str | None = None,
               type: str | None = None, category: str | None = None,
               amount: str | int | None = None, memo: str | None = None,
               tags: str | None = None) -> Transaction:
        changes: dict[str, Any] = {}
        if date is not None:
            changes["date"] = parse_date(date)
        if type is not None:
            changes["type"] = parse_type(type)
        if category is not None:
            changes["category"] = self._categories.require(category)
        if amount is not None:
            changes["amount"] = parse_amount(amount)
        if memo is not None:
            changes["memo"] = memo.strip()
        if tags is not None:
            changes["tags"] = parse_tags(tags)
        if not changes:
            raise ValidationError(
                "수정할 항목이 없습니다.",
                "--date --type --category --amount --memo --tags 중 하나 이상을 지정하세요.",
            )
        old = self._repo.get(tx_id)
        if old is None:
            raise NotFoundError(
                f"존재하지 않는 거래 id 입니다: {tx_id}",
                "list 명령으로 id 를 확인하세요.",
            )
        new = replace(old, **changes)
        self._repo.update(tx_id, new)
        return new

    @log_call
    def delete(self, tx_id: str) -> None:
        self._repo.delete(tx_id)

    def list_recent(self, limit: int) -> list[Transaction]:
        return self.search(SearchCriteria(), limit)

    def make_criteria(self, *, date_from: str | None = None,
                      date_to: str | None = None, category: str | None = None,
                      type: str | None = None, q: str | None = None,
                      tag: str | None = None) -> SearchCriteria:
        start = parse_date(date_from) if date_from else None
        end = parse_date(date_to) if date_to else None
        if start and end and start > end:
            raise ValidationError(
                "--from 날짜가 --to 날짜보다 늦습니다.",
                "기간의 시작과 끝 순서를 바꿔 보세요.",
            )
        return SearchCriteria(
            date_from=start,
            date_to=end,
            category=category.strip() if category else None,
            type=parse_type(type) if type else None,
            q=q.strip() if q else None,
            tag=tag.strip() if tag else None,
        )

    def stream_matching(self, criteria: SearchCriteria) -> Iterator[Transaction]:
        return (tx for tx in self._repo.stream_all() if criteria.matches(tx))

    @timed
    def search(self, criteria: SearchCriteria, limit: int | None = None) -> list[Transaction]:
        """최신순((date, id) 내림차순). limit 이 있으면 메모리는 O(limit)."""
        matches = self.stream_matching(criteria)
        if limit is None:
            return sorted(matches, key=_sort_key, reverse=True)
        if limit <= 0:
            raise ValidationError(
                "--limit 은 1 이상이어야 합니다.", "예: --limit 10"
            )
        return heapq.nlargest(limit, matches, key=_sort_key)


class BudgetService:
    def __init__(self, store: BudgetStore) -> None:
        self._store = store

    @log_call
    def set(self, month: str, amount: str | int) -> Budget:
        budget = Budget(parse_month(month), parse_amount(amount))
        self._store.set(budget)
        return budget

    def get(self, month: str) -> Budget | None:
        return self._store.get(parse_month(month))


class ReportService:
    def __init__(self, repo: TransactionRepository, budgets: BudgetService) -> None:
        self._repo = repo
        self._budgets = budgets

    @timed
    def monthly_summary(self, month: str, top_n: int = 3) -> MonthlySummary:
        month = parse_month(month)
        if top_n <= 0:
            raise ValidationError("--top 은 1 이상이어야 합니다.", "예: --top 3")
        prefix = month + "-"
        income = expense = count = 0
        by_category: Counter[str] = Counter()
        for tx in self._repo.stream_all():
            if not tx.date.startswith(prefix):
                continue
            count += 1
            if tx.type == "income":
                income += tx.amount
            else:
                expense += tx.amount
                by_category[tx.category] += tx.amount
        top = sorted(by_category.items(), key=lambda kv: (-kv[1], kv[0]))[:top_n]
        budget = self._budgets.get(month)
        usage: float | None = None
        over = False
        if budget is not None and count > 0:
            usage = round(expense / budget.amount * 100, 1)
            over = expense > budget.amount
        return MonthlySummary(
            month=month,
            tx_count=count,
            total_income=income,
            total_expense=expense,
            balance=income - expense,
            top_expenses=tuple(top),
            budget=budget,
            usage_percent=usage,
            over_budget=over,
        )


class CsvService:
    def __init__(self, repo: TransactionRepository, tx_service: TransactionService,
                 categories: CategoryService) -> None:
        self._repo = repo
        self._tx_service = tx_service
        self._categories = categories

    @log_call
    @timed
    def export(self, out: Path, *, month: str | None = None,
               date_from: str | None = None, date_to: str | None = None) -> int:
        if not month and not date_from and not date_to:
            raise ValidationError(
                "내보낼 기간 조건이 없습니다.",
                "--month YYYY-MM 또는 --from YYYY-MM-DD --to YYYY-MM-DD 를 지정하세요.",
            )
        if month:
            month = parse_month(month)
        criteria = self._tx_service.make_criteria(date_from=date_from, date_to=date_to)
        prefix = month + "-" if month else None
        rows = (
            tx for tx in self._tx_service.stream_matching(criteria)
            if prefix is None or tx.date.startswith(prefix)
        )
        return csv_io.write_transactions(out, rows)

    @log_call
    @timed
    def import_(self, src: Path) -> ImportResult:
        """모든 행을 먼저 검증하고, 통과한 행만 한 번에 append 한다."""
        valid: list[dict[str, Any]] = []
        errors: list[str] = []
        known = set(self._categories.list())
        for line_no, row in csv_io.read_rows(src):
            try:
                category = parse_category_name(row.get("category", ""))
                if category not in known:
                    self._categories.require(category)
                valid.append({
                    "date": parse_date(row.get("date", "")),
                    "type": parse_type(row.get("type", "")),
                    "category": category,
                    "amount": parse_amount(row.get("amount", "")),
                    "memo": row.get("memo", ""),
                    "tags": parse_tags(row.get("tags", "")),
                })
            except (ValidationError, NotFoundError) as exc:
                errors.append(f"{line_no}번째 줄: {exc.message}")
        ids = self._repo.next_ids(len(valid))
        self._repo.append_many(Transaction(id=i, **v) for i, v in zip(ids, valid))
        return ImportResult(len(valid), len(errors), tuple(errors))


class AppContext:
    """서비스 객체들을 조립한다."""

    def __init__(self, storage: Storage) -> None:
        self.storage = storage
        self.categories = CategoryService(storage.categories, storage.transactions)
        self.transactions = TransactionService(storage.transactions, self.categories)
        self.budgets = BudgetService(storage.budgets)
        self.reports = ReportService(storage.transactions, self.budgets)
        self.csv = CsvService(storage.transactions, self.transactions, self.categories)
