"""출력 문자열 생성. 외부 라이브러리 없이 문자열 정렬만 사용한다."""

from __future__ import annotations

import unicodedata
from typing import Sequence

from .models import MonthlySummary, Transaction


def display_width(text: str) -> int:
    """터미널에서 차지하는 칸 수. 한글 등 전각 문자는 2칸."""
    return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in text)


def pad(text: str, width: int, *, right: bool = False) -> str:
    gap = " " * max(0, width - display_width(text))
    return gap + text if right else text + gap


def format_transactions(transactions: Sequence[Transaction]) -> list[str]:
    """id | date | type | category | amount | memo 형태로 컬럼을 정렬한다."""
    rows = [
        (
            tx.id, tx.date, tx.type, tx.category, str(tx.amount),
            (tx.memo + "  " + " ".join(f"#{t}" for t in tx.tags)).strip(),
        )
        for tx in transactions
    ]
    if not rows:
        return []
    widths = [max(display_width(row[i]) for row in rows) for i in range(5)]
    lines = []
    for row in rows:
        cells = [pad(row[i], widths[i], right=(i == 4)) for i in range(5)]
        cells.append(row[5])
        lines.append(" | ".join(cells).rstrip())
    return lines


def format_summary(summary: MonthlySummary) -> list[str]:
    if summary.tx_count == 0:
        lines = [f"[{summary.month}] 데이터 없음"]
        if summary.budget is not None:
            lines.append(f"예산: {summary.budget.amount}원 (이 달의 거래 내역이 없습니다)")
        return lines

    lines = [
        f"[{summary.month} 월별 요약]",
        f"총 수입: {summary.total_income}원",
        f"총 지출: {summary.total_expense}원",
        f"잔액: {summary.balance}원",
    ]
    if summary.budget is not None and summary.usage_percent is not None:
        lines.append(
            f"예산: {summary.budget.amount}원 (사용률 {summary.usage_percent:.1f}%)"
        )
        if summary.over_budget:
            over = summary.total_expense - summary.budget.amount
            lines.append(f"[경고] 예산을 {over}원 초과했습니다!")
    else:
        lines.append("예산: 설정되지 않음")

    lines.append("")
    if summary.top_expenses:
        lines.append(f"지출 TOP {len(summary.top_expenses)}")
        for rank, (category, amount) in enumerate(summary.top_expenses, start=1):
            lines.append(f"{rank}) {category} {amount}원")
    else:
        lines.append("지출 내역 없음")
    return lines
