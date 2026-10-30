"""명령행 파싱, 대화형 입력, 출력, 종료 코드. 비즈니스 규칙은 services 에 맡긴다."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Callable, Sequence, TypeVar

from . import __version__
from .decorators import handle_errors, logger
from .formatters import format_summary, format_transactions
from .models import (
    BudgetAppError,
    Transaction,
    parse_amount,
    parse_date,
    parse_tags,
    parse_type,
)
from .services import AppContext
from .storage import Storage

DEFAULT_DATA_DIR = "./data"
DEFAULT_LIST_LIMIT = 20
DEFAULT_TOP = 3

T = TypeVar("T")


# ---------------------------------------------------------------- 입출력 보조
def _print_error(exc: BudgetAppError) -> None:
    print(f"[오류] {exc.message}", file=sys.stderr)
    if exc.hint:
        print(f"[힌트] {exc.hint}", file=sys.stderr)


def _prompt(label: str, parse: Callable[[str], T]) -> T:
    """검증에 통과할 때까지 같은 항목을 다시 묻는다."""
    while True:
        raw = input(label)
        try:
            return parse(raw)
        except BudgetAppError as exc:
            _print_error(exc)


# ---------------------------------------------------------------- 명령 핸들러
def cmd_add(args: argparse.Namespace, ctx: AppContext) -> int:
    date = _prompt("날짜(YYYY-MM-DD): ", parse_date)
    tx_type = _prompt("타입(income/expense): ", parse_type)
    category = _prompt("카테고리: ", ctx.categories.require)
    amount = _prompt("금액(양수): ", parse_amount)
    memo = input("메모(선택): ")
    tags = input("태그(쉼표로 구분, 없으면 엔터): ")
    tx = ctx.transactions.add(
        date=date, type=tx_type, category=category, amount=amount,
        memo=memo, tags=",".join(parse_tags(tags)),
    )
    print(f"[저장 완료] id={tx.id}")
    return 0


def _print_transactions(transactions: Sequence[Transaction]) -> None:
    lines = format_transactions(transactions)
    if not lines:
        print("조건에 맞는 거래가 없습니다.")
        return
    print("\n".join(lines))


def cmd_list(args: argparse.Namespace, ctx: AppContext) -> int:
    _print_transactions(ctx.transactions.list_recent(args.limit))
    return 0


def cmd_search(args: argparse.Namespace, ctx: AppContext) -> int:
    criteria = ctx.transactions.make_criteria(
        date_from=args.date_from, date_to=args.date_to, category=args.category,
        type=args.type, q=args.q, tag=args.tag,
    )
    _print_transactions(ctx.transactions.search(criteria, args.limit))
    return 0


def cmd_summary(args: argparse.Namespace, ctx: AppContext) -> int:
    summary = ctx.reports.monthly_summary(args.month, args.top)
    print("\n".join(format_summary(summary)))
    return 0


def cmd_budget_set(args: argparse.Namespace, ctx: AppContext) -> int:
    budget = ctx.budgets.set(args.month, args.amount)
    print(f"[저장 완료] {budget.month} 예산 {budget.amount}원")
    return 0


def cmd_budget_show(args: argparse.Namespace, ctx: AppContext) -> int:
    budget = ctx.budgets.get(args.month)
    if budget is None:
        print(f"{args.month} 에 설정된 예산이 없습니다.")
        print(f"[힌트] budget set --month {args.month} --amount <금액>")
    else:
        print(f"{budget.month} 예산: {budget.amount}원")
    return 0


def cmd_category_add(args: argparse.Namespace, ctx: AppContext) -> int:
    if args.name is None:
        name = _prompt("카테고리명: ", ctx.categories.add)
    else:
        name = ctx.categories.add(args.name)
    print(f"[저장 완료] category={name}")
    return 0


def cmd_category_list(args: argparse.Namespace, ctx: AppContext) -> int:
    names = ctx.categories.list()
    if not names:
        print("등록된 카테고리가 없습니다.")
        print("[힌트] category add --name <이름>")
        return 0
    print("\n".join(f"- {n}" for n in names))
    return 0


def cmd_category_remove(args: argparse.Namespace, ctx: AppContext) -> int:
    name = ctx.categories.remove(args.name)
    print(f"[삭제 완료] category={name}")
    return 0


def cmd_update(args: argparse.Namespace, ctx: AppContext) -> int:
    tx = ctx.transactions.update(
        args.id, date=args.date, type=args.type, category=args.category,
        amount=args.amount, memo=args.memo, tags=args.tags,
    )
    print(f"[수정 완료] id={tx.id}")
    print("\n".join(format_transactions([tx])))
    return 0


def cmd_delete(args: argparse.Namespace, ctx: AppContext) -> int:
    ctx.transactions.delete(args.id)
    print(f"[삭제 완료] id={args.id}")
    return 0


def cmd_import(args: argparse.Namespace, ctx: AppContext) -> int:
    result = ctx.csv.import_(Path(args.src))
    print(f"[완료] imported={result.imported}, skipped={result.skipped}")
    for message in result.errors:
        print(f"  - {message}", file=sys.stderr)
    return 0


def cmd_export(args: argparse.Namespace, ctx: AppContext) -> int:
    count = ctx.csv.export(
        Path(args.out), month=args.month,
        date_from=args.date_from, date_to=args.date_to,
    )
    print(f"[완료] {args.out} ({count} records)")
    return 0


# ---------------------------------------------------------------- 파서
def build_parser() -> argparse.ArgumentParser:
    # SUPPRESS: 서브커맨드 앞/뒤 어디에 써도 받고, 안 쓰면 속성 자체가 생기지 않는다.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--data-dir", default=argparse.SUPPRESS, metavar="DIR",
        help=f"데이터 저장 폴더 (기본: {DEFAULT_DATA_DIR})",
    )
    common.add_argument(
        "--verbose", action="store_true", default=argparse.SUPPRESS,
        help="실행 로그를 stderr 로도 출력",
    )

    parser = argparse.ArgumentParser(
        prog="budget_app", parents=[common],
        description="콘솔 가계부 (파일 기반 저장)",
    )
    parser.add_argument("--version", action="version", version=f"budget_app {__version__}")
    sub = parser.add_subparsers(dest="command", required=True, metavar="<command>")

    def leaf(group: argparse._SubParsersAction[argparse.ArgumentParser],  # noqa: SLF001
             name: str, help_text: str,
             func: Callable[[argparse.Namespace, AppContext], int]) -> argparse.ArgumentParser:
        p = group.add_parser(name, parents=[common], help=help_text, description=help_text)
        p.set_defaults(func=func)
        return p

    leaf(sub, "add", "거래 추가 (대화형 입력)", cmd_add)

    p = leaf(sub, "list", "거래 목록 (최신순)", cmd_list)
    p.add_argument("--limit", type=int, default=DEFAULT_LIST_LIMIT,
                   help=f"출력할 최대 건수 (기본: {DEFAULT_LIST_LIMIT})")

    p = leaf(sub, "search", "조건으로 거래 검색 (최신순)", cmd_search)
    p.add_argument("--from", dest="date_from", metavar="YYYY-MM-DD", help="시작일 (포함)")
    p.add_argument("--to", dest="date_to", metavar="YYYY-MM-DD", help="종료일 (포함)")
    p.add_argument("--category", help="카테고리")
    p.add_argument("--type", choices=["income", "expense"], help="거래 타입")
    p.add_argument("--q", help="메모에 포함된 키워드 (대소문자 무시)")
    p.add_argument("--tag", help="태그")
    p.add_argument("--limit", type=int, default=None, help="출력할 최대 건수 (기본: 전부)")

    p = leaf(sub, "summary", "월별 요약과 예산 사용률", cmd_summary)
    p.add_argument("--month", required=True, metavar="YYYY-MM", help="요약할 월")
    p.add_argument("--top", type=int, default=DEFAULT_TOP,
                   help=f"카테고리별 지출 TOP N (기본: {DEFAULT_TOP})")

    budget = sub.add_parser("budget", parents=[common], help="월 예산 설정/조회")
    bsub = budget.add_subparsers(dest="action", required=True, metavar="<action>")
    p = leaf(bsub, "set", "월 예산 설정", cmd_budget_set)
    p.add_argument("--month", required=True, metavar="YYYY-MM", help="예산 월")
    p.add_argument("--amount", required=True, help="예산 금액 (양수 정수)")
    p = leaf(bsub, "show", "월 예산 조회", cmd_budget_show)
    p.add_argument("--month", required=True, metavar="YYYY-MM", help="조회할 월")

    category = sub.add_parser("category", parents=[common], help="카테고리 관리")
    csub = category.add_subparsers(dest="action", required=True, metavar="<action>")
    p = leaf(csub, "add", "카테고리 추가 (--name 이 없으면 대화형 입력)", cmd_category_add)
    p.add_argument("--name", help="카테고리명")
    leaf(csub, "list", "카테고리 목록", cmd_category_list)
    p = leaf(csub, "remove", "카테고리 삭제 (사용 중이면 거부)", cmd_category_remove)
    p.add_argument("--name", required=True, help="삭제할 카테고리명")

    p = leaf(sub, "update", "거래 수정 (옵션 방식, 지정한 항목만 변경)", cmd_update)
    p.add_argument("--id", required=True, help="수정할 거래 id (예: TX-000012)")
    p.add_argument("--date", metavar="YYYY-MM-DD", help="새 날짜")
    p.add_argument("--type", choices=["income", "expense"], help="새 타입")
    p.add_argument("--category", help="새 카테고리")
    p.add_argument("--amount", help="새 금액 (양수 정수)")
    p.add_argument("--memo", help="새 메모 (빈 문자열이면 비움)")
    p.add_argument("--tags", help="새 태그, 쉼표 구분 (빈 문자열이면 비움)")

    p = leaf(sub, "delete", "거래 삭제", cmd_delete)
    p.add_argument("--id", required=True, help="삭제할 거래 id")

    p = leaf(sub, "import", "CSV 에서 거래 가져오기", cmd_import)
    p.add_argument("--from", dest="src", required=True, metavar="CSV", help="가져올 CSV 파일")

    p = leaf(sub, "export", "조건에 맞는 거래를 CSV 로 내보내기", cmd_export)
    p.add_argument("--out", required=True, metavar="CSV", help="저장할 CSV 파일")
    p.add_argument("--month", metavar="YYYY-MM", help="내보낼 월")
    p.add_argument("--from", dest="date_from", metavar="YYYY-MM-DD", help="시작일 (포함)")
    p.add_argument("--to", dest="date_to", metavar="YYYY-MM-DD", help="종료일 (포함)")

    return parser


# ---------------------------------------------------------------- 실행
def _setup_logging(data_dir: Path, verbose: bool) -> None:
    _teardown_logging()
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    handlers: list[logging.Handler] = [
        logging.FileHandler(data_dir / "budget.log", encoding="utf-8")
    ]
    if verbose:
        handlers.append(logging.StreamHandler(sys.stderr))
    for handler in handlers:
        handler.setFormatter(formatter)
        logger.addHandler(handler)


def _teardown_logging() -> None:
    for handler in list(logger.handlers):
        if not isinstance(handler, logging.NullHandler):
            logger.removeHandler(handler)
            handler.close()


@handle_errors
def run(args: argparse.Namespace) -> int:
    storage = Storage(getattr(args, "data_dir", DEFAULT_DATA_DIR))
    notices = storage.initialize()
    _setup_logging(storage.data_dir, getattr(args, "verbose", False))
    for notice in notices:
        print(notice, file=sys.stderr)
    logger.info("command=%s", args.command)
    return int(args.func(args, AppContext(storage)))


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return run(args)
    finally:
        _teardown_logging()
