"""공통 관심사(로그, 실행 시간, 예외 → 종료 코드)를 비즈니스 로직에서 분리한다."""

from __future__ import annotations

import functools
import logging
import sys
import time
from typing import Callable, ParamSpec, TypeVar

from .models import BudgetAppError

P = ParamSpec("P")
R = TypeVar("R")

logger = logging.getLogger("budget_app")
# 핸들러가 없을 때 logging 이 경고를 stderr 로 직접 찍지 않도록 한다.
logger.addHandler(logging.NullHandler())

EXIT_INTERNAL = 70
EXIT_INTERRUPTED = 130
EXIT_STORAGE = 2


def _summarize(func: Callable[..., object], args: tuple[object, ...],
               kwargs: dict[str, object]) -> str:
    is_method = "." in func.__qualname__.split("<locals>")[-1]
    shown = args[1:] if is_method else args
    parts = [repr(a) for a in shown] + [f"{k}={v!r}" for k, v in kwargs.items()]
    text = ", ".join(parts)
    return text if len(text) <= 120 else text[:117] + "..."


def log_call(func: Callable[P, R]) -> Callable[P, R]:
    """호출, 성공, 실패를 로그로 남긴다."""

    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        name = func.__qualname__
        logger.info("call %s(%s)", name, _summarize(func, args, kwargs))
        try:
            result = func(*args, **kwargs)
        except Exception as exc:
            logger.warning("fail %s: %s: %s", name, type(exc).__name__, exc)
            raise
        logger.info("ok   %s", name)
        return result

    return wrapper


def timed(func: Callable[P, R]) -> Callable[P, R]:
    """실행 시간을 측정해 로그로 남긴다."""

    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        start = time.perf_counter()
        try:
            return func(*args, **kwargs)
        finally:
            elapsed = (time.perf_counter() - start) * 1000
            logger.info("time %s %.1fms", func.__qualname__, elapsed)

    return wrapper


def _report(message: str, hint: str) -> None:
    print(f"[오류] {message}", file=sys.stderr)
    if hint:
        print(f"[힌트] {hint}", file=sys.stderr)


def handle_errors(func: Callable[P, int]) -> Callable[P, int]:
    """예외를 '원인 + 힌트' 메시지와 종료 코드로 바꾼다. 스택트레이스는 출력하지 않는다."""

    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> int:
        try:
            return func(*args, **kwargs)
        except BudgetAppError as exc:
            _report(exc.message, exc.hint)
            return exc.exit_code
        except (KeyboardInterrupt, EOFError):
            print("\n[취소] 입력이 취소되었습니다.", file=sys.stderr)
            return EXIT_INTERRUPTED
        except OSError as exc:
            logger.exception("OS error")
            _report(
                f"파일을 처리하지 못했습니다: {exc.strerror or exc}",
                "경로와 접근 권한을 확인하세요. (--data-dir 로 다른 폴더를 지정할 수 있습니다)",
            )
            return EXIT_STORAGE
        except Exception as exc:  # noqa: BLE001 - 최후의 방어선
            logger.exception("unexpected error")
            _report(
                f"예기치 못한 오류가 발생했습니다: {type(exc).__name__}",
                "data 폴더의 budget.log 에 상세 내용이 기록되어 있습니다.",
            )
            return EXIT_INTERNAL

    return wrapper
