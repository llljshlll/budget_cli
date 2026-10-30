# 콘솔 가계부
---

## 1. 프로젝트 개요

### 만든 것

Python 표준 라이브러리만 사용한 **콘솔 가계부**
 터미널에서 명령어로 수입/지출을 기록하고, 조회·검색·수정·삭제하고, 월별 요약과 예산 초과 경고를 볼 수 있음. 데이터는 파일에 저장되어서 프로그램을 껐다 켜도 남음

```bash
python3 -m budget_app add        # 대화형으로 거래 추가
python3 -m budget_app list       # 최신순 목록
python3 -m budget_app summary --month 2026-10
```


---

## 2. 요구사항과 구현 결과  

### 필수 기능 10가지

| # | 기능 | 명령 |
| --- | --- | --- |
| 1 | 거래 추가 | `add` |
| 2 | 거래 목록 | `list --limit N` |
| 3 | 거래 검색 | `search --from --to --category --type --q --tag` |
| 4 | 월별 요약 | `summary --month --top` |
| 5 | 예산 설정/조회 | `budget set`, `budget show` |
| 6 | 카테고리 관리 | `category add/list/remove` |
| 7 | 거래 수정 | `update --id ...` |
| 8 | 거래 삭제 | `delete --id` |
| 9 | 가져오기 | `import --from` |
| 10 | 내보내기 | `export --out --month` |

### 공통 요구사항

| 요구사항 | 구현 | 위치 |
| --- | --- | --- |
| 모든 명령에 `--help` | argparse 서브커맨드 | `build_parser` cli.py:177 |
| 옵션은 `--`로 통일 | 모든 옵션이 `--` | cli.py |
| Transaction은 dataclass, 클래스 2개 이상 | `Transaction`, `Budget` 등 dataclass + 저장소/서비스 클래스 | models.py, storage.py, services.py |
| 입력 검증 (날짜·금액·타입·카테고리) | `parse_*` 함수와 `CategoryService.require` | models.py:53~110, services.py:44 |
| 저장 파일 3개 이상 + `--data-dir` | `Storage` 클래스 | storage.py:209 |
| 첫 실행 시 자동 생성 + 기본 카테고리 | `initialize`, `ensure_defaults` | storage.py:220, :175 |
| list/search는 제너레이터 + 최신순 | `stream()` + `heapq.nlargest` | storage.py:46, services.py:169 |
| update/delete는 안전한 파일 교체 | 임시 파일 + `os.replace` | storage.py:78 (`rewrite`) |
| 카테고리 삭제 시 사용 중이면 차단 | `CategoryInUseError` | services.py:62 |
| import/export CSV 스키마 고정 | `COLUMNS`, `REQUIRED_COLUMNS` | csv_io.py:13 |
| 데코레이터 1개 이상 적용 | 구현, 실제 적용 | decorators.py |
| 스택트레이스 금지, 종료 코드 | `handle_errors` | decorators.py:73 |
| 모듈 3개 이상 | 8개 | `budget_app/` |
| 표준 라이브러리만 사용 | 외부 import 없음 | 전체 |

### 설계 선택

| 선택 | 이유 |
| --- | --- |
| 저장 포맷은 **JSONL** | 한 줄이 한 레코드라 한 줄씩 읽는 스트리밍에 적합, tags를 리스트 그대로 저장 가능 (9번 비교는 4장) |
| update는 **옵션 방식** | `update --id X --amount 5000`처럼 바꿀 항목만 적을 수 있고 테스트가 쉬움 |
| 사용 중인 카테고리는 **삭제 차단** | 거래가 존재하지 않는 카테고리를 가리키는 상황을 원천 차단하는 가장 단순한 방법 |
| 최신순 기준은 `(날짜, id)` 내림차순 | 날짜가 같으면 나중에 만든 거래가 먼저 나옴 |

---

## 3. 전체 아키텍처

### 디렉터리 구조

```
budget-cli/
├── budget_app/
│   ├── __main__.py     python -m budget_app 진입점
│   ├── cli.py          명령 파싱, 대화형 입력, 출력, 종료 코드
│   ├── services.py     업무 규칙 (검증 조합, 검색, 집계, import/export 흐름)
│   ├── storage.py      파일 읽기/쓰기 (JSONL), 스트리밍, 원자적 교체
│   ├── models.py       dataclass, 입력 검증 함수, 예외 클래스
│   ├── csv_io.py       CSV 스키마와 읽기/쓰기
│   ├── formatters.py   출력 문자열 (한글 폭을 고려한 표 정렬)
│   └── decorators.py   handle_errors / log_call / timed
├── data/               실행 시 생성되는 저장 폴더
│   ├── transactions.jsonl
│   ├── categories.jsonl
│   ├── budgets.jsonl
│   └── budget.log
└── README.md
```

### 모듈 관계

호출은 위에서 아래로만 흐르며, **아래 계층은 위 계층을 import하지 않음**

```
          사용자
            │  명령어 / input()
            ▼
   ┌─────────────────┐
   │     cli.py      │  입력 받기, 출력하기, 종료 코드
   └───────┬─────────┘
           │ (formatters.py로 출력 모양 만들기)
           ▼
   ┌─────────────────┐
   │   services.py   │  "카테고리가 있나?", "예산을 넘었나?" 같은 규칙
   └───────┬─────────┘
           ▼
   ┌─────────────────┐
   │   storage.py    │  파일 읽기/쓰기만 담당 (규칙은 모름)
   └───────┬─────────┘
           ▼
     data/*.jsonl

 models.py : 모든 계층이 같이 쓰는 데이터 구조 + 검증 + 예외
 decorators.py : 서비스/진입점에 덧붙는 공통 기능
```

### 클래스의 책임 경계

| 계층 | 클래스 | 맡은 일 | 모르는 것 |
| --- | --- | --- | --- |
| storage | `JsonlFile[T]` | 한 줄씩 읽기, append, 안전하게 다시 쓰기 | 거래의 정의 |
| storage | `TransactionRepository` | 거래의 id 발급, 조회, 수정, 삭제 | 카테고리 규칙 |
| storage | `CategoryStore`, `BudgetStore` | 카테고리/예산 파일 읽기·쓰기 | 업무 규칙 |
| storage | `Storage` | 파일 3개를 묶고 첫 실행 때 초기화 | |
| services | `CategoryService` | 카테고리 존재 확인, 삭제 차단 | 파일 형식 |
| services | `TransactionService` | 거래 추가·수정·삭제·검색 | 화면 출력 |
| services | `BudgetService` | 예산 저장/조회 | |
| services | `ReportService` | 월별 합계, TOP N, 사용률 계산 | |
| services | `CsvService` | import/export 전체 흐름 | |
| services | `AppContext` | 위 서비스들을 한 번에 조립 | |
| cli | 함수 `cmd_*` | 입력 받고 서비스 호출하고 출력 | 규칙 판단 |

**예시**: "사용 중인 카테고리는 삭제 불가"라는 규칙은 `CategoryService.remove`(services.py:62)에만 존재. 저장소는 지우는 일만 담당, CLI는 서비스가 던진 예외를 메시지로 보여줄 뿐. 규칙 변경 시 고칠 곳은 한 군데

### 데이터 흐름 (거래 추가)

```
add 입력
  → cli.cmd_add ─ 날짜/타입/금액/카테고리를 하나씩 검증하며 입력받음
  → TransactionService.add ─ 다시 한 번 검증 + 카테고리 확인
  → TransactionRepository.next_id ─ 파일을 훑어 가장 큰 번호 + 1
  → JsonlFile.append_many ─ 파일 끝에 한 줄 추가 + fsync
  → "[저장 완료] id=TX-000012" 출력
```

### 저장 파일 3개

| 파일 | 한 줄 예시 |
| --- | --- |
| `transactions.jsonl` | `{"id":"TX-000001","type":"expense","date":"2026-10-15","amount":18000,"category":"food","memo":"점심","tags":["meal"]}` |
| `categories.jsonl` | `{"name":"food"}` |
| `budgets.jsonl` | `{"month":"2026-10","amount":100000}` |

---

## 4. 핵심 기술 설명

### 4.1 Generator (제너레이터)

**한 줄 정의**: 값을 `return`으로 한꺼번에 주지 않고 `yield`로 **하나씩 건네주는** 함수.


```python
def stream(self) -> Iterator[T]:
    with self.path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            ...
            yield item        # 한 건을 돌려주고, 다음 요청이 올 때까지 정지
```

**사용 이유**: `list`로 전부 읽으면 거래 수만큼 메모리 사용. 제너레이터는 필요한 만큼만 읽음

**측정 결과** (35MB, 30만 건 파일)

| 방식 | 최대 메모리 |
| --- | --- |
| 이 프로그램의 `list --limit 3` | 약 20MB |
| `summary --month 2026-05` | 약 21MB |
| 비교: 파일 전체를 리스트로 읽기 | 약 299MB |

`list`, `search`, `summary`, `export`가 모두 같은 `stream()`을 한 번 훑는 방식으로 동작

**한계**: `search`를 `--limit` 없이 쓰면 조건에 맞는 거래 전부를 정렬해야 하므로 그 건수만큼 메모리 사용

### 4.2 Decorator (데코레이터)

**한 줄 정의**: 함수를 감싸서 **원래 코드를 건드리지 않고** 기능을 덧붙이는 문법. 


| 데코레이터 | 하는 일 | 붙인 곳 |
| --- | --- | --- |
| `@handle_errors` (:73) | 예외를 `[오류]/[힌트]` 메시지와 종료 코드로 바꿈 | `run()` (cli.py:285) |
| `@log_call` (:34) | 호출·성공·실패를 `budget.log`에 기록 | `add`/`update`/`delete`/`set`/`remove`/`import_`/`export` |

```python
def log_call(func):
    @functools.wraps(func)                 # 원래 함수의 이름/설명을 유지
    def wrapper(*args, **kwargs):
        logger.info("call %s(...)", func.__qualname__)
        try:
            result = func(*args, **kwargs)  # 원래 함수 실행
        except Exception:
            logger.warning("fail ...")
            raise                           # 예외는 그대로 다시 던짐
        logger.info("ok   %s", ...)
        return result
    return wrapper
```

**사용 이유**: 서비스 메서드마다 로그와 try/except를 쓰면 중복 발생, 본래 로직 은폐. 데코레이터 사용 시 서비스 코드에는 업무 규칙만 남음


### 4.3 Type Hint (타입 힌트)

**한 줄 정의**: 함수의 인자와 반환값이 어떤 타입인지 **코드에 미리 적어 두는** 표기. 실행을 막지는 않지만 읽는 사람과 도구에게 약속 역할

**내 코드에서 눈에 띄는 것**

| 표기 | 의미 |
| --- | --- |
| `TxType = Literal["income", "expense"]` | 거래 타입은 이 두 문자열만 허용된다는 약속 |
| `def stream(self) -> Iterator[T]` | "한 건씩 흘려보낸다"는 사실이 시그니처에 드러남 |
| `def get(self, tx_id: str) -> Transaction \| None` | 결과가 **없을 수도 있다**고 호출하는 쪽에 알림 |
| `def parse_amount(value: str \| int) -> int` | 문자열이나 정수를 받아 항상 양의 정수를 돌려줌 |

**얻는 이점**: 함수 정의만 읽어도 무엇을 넣고 무엇이 나오는지 파악 가능. 에디터가 오타나 타입 불일치를 미리 알려 줌

**주의**: 타입을 자동 검사하는 도구(mypy)는 미설치로 실행하지 않음. 타입 힌트는 문서화와 에디터 지원 용도로 사용


### 4.4 파일 I/O

| 동작 | 방법 |
| --- | --- |
| 읽기 | `open()`을 열고 한 줄씩 순회하며 `yield` |
| 추가 | `"a"` 모드로 열어 한 줄 쓰고 `flush` + `fsync` |
| 수정·삭제 | 임시 파일에 전부 쓰고 `os.replace`로 교체 |
| 인코딩 | 항상 UTF-8, `ensure_ascii=False`로 한글 그대로 저장 |

**JSONL과 CSV 차이**

| | JSONL | CSV |
| --- | --- | --- |
| 모양 | 한 줄 = JSON 객체 하나 | 표 (헤더 + 행) |
| 장점 | 리스트·중첩 구조를 그대로 저장, 한 줄씩 읽기 쉬움 | 엑셀로 바로 열림 |
| 약점 | 사람이 보기에 불편 | 태그 같은 리스트를 문자열로 이어 붙여야 하고, 쉼표/따옴표 처리가 필요 |
| 이 프로젝트에서 | **내부 저장** | **import/export 교환용** |

**CSV 스키마** — `csv_io.py:13`

| column | 필수 | 설명 |
| --- | --- | --- |
| date | Y | `YYYY-MM-DD` |
| type | Y | `income` / `expense` |
| category | Y | 등록된 카테고리 |
| amount | Y | 양수 정수 |
| memo | N | 문자열 |
| tags | N | 쉼표 구분 문자열 (CSV에서는 따옴표로 감싸짐) |

UTF-8, 첫 줄은 헤더. 컬럼 순서는 무관. 필수 컬럼이 빠지면 파일 전체 거부

---


## 5. 예외 처리와 데이터 안전성

### 5.1 예외 구조

`models.py:19`의 `BudgetAppError`가 모든 앱 예외의 부모 클래스이며, **원인(message)** 과 **해결 힌트(hint)** 를 항상 보유

```
BudgetAppError
├── ValidationError     입력값이 규칙에 안 맞음 (날짜/금액/타입/기간)
├── NotFoundError       없는 id, 등록되지 않은 카테고리
├── DuplicateError      이미 있는 카테고리
├── CategoryInUseError  거래가 쓰는 카테고리 삭제 시도
└── StorageError        저장 파일 손상 또는 쓰기 불가
```

`@handle_errors`(decorators.py:73)가 이 예외를 잡아 다음 형태로 출력. **스택트레이스는 화면에 미출력**

```
[오류] 날짜 형식이 올바르지 않습니다 (YYYY-MM-DD).
[힌트] 예: 2026-10-15
```

### 5.2 종료 코드

| 코드 | 상황 |
| --- | --- |
| 0 | 정상 |
| 1 | 입력 오류, 없는 id/카테고리, 사용 중인 카테고리 삭제 |
| 2 | 저장 파일/경로 오류, 명령 사용법 오류 |
| 70 | 예상하지 못한 오류 (상세는 `budget.log`에만 기록) |
| 130 | 입력 취소 (Ctrl+C, 입력 도중 EOF) |

### 5.3 비정상 입력 처리

| 입력 | 결과 |
| --- | --- |
| `2026-13-40` (잘못된 날짜) | 오류 + 힌트, `add`에서는 같은 항목 재입력 |
| 금액 `0`, `-5`, `abc`, `1.5` | 거부 |
| 타입이 `income`/`expense`가 아님 | 거부 |
| 등록되지 않은 카테고리 | 등록된 목록과 `category add` 안내 후 재입력 |
| 없는 id의 `update`/`delete` | `존재하지 않는 거래 id`, 종료 코드 1 |
| `update`에 바꿀 항목 없음 | 거부 |
| 사용 중인 카테고리 삭제 | 거부 + 사용 건수 안내 |
| `export`에 기간 조건 없음 | 거부 |
| `--from`이 `--to`보다 늦음 | 거부 |
| `import` CSV 헤더에 필수 컬럼 없음 | 파일 전체 거부 |
| `import` 일부 행이 잘못됨 | 그 행만 건너뛰고 나머지는 반영 |
| 명령 옵션 누락/잘못된 값 | `[오류]`/`[힌트]` 형식, 종료 코드 2 |

### 5.4 파일 손상 방지

| 위험 | 대응 |
| --- | --- |
| 수정/삭제 도중 프로그램이 멈춤 | 원본은 건드리지 않고 임시 파일에 쓴 뒤 `os.replace`로 교체. 실패하면 임시 파일만 삭제 |
| 교체 직전 디스크 오류 | 같은 방식으로 원본 유지 (테스트에서 `os.replace`를 강제로 실패시켜 확인) |
| 파일 내용이 깨져 있음 | `N번째 줄을 읽을 수 없습니다`와 해결 힌트를 보여주고 종료 (조용히 무시하지 않음) |
| 쓰기 권한 없음, 데이터 경로가 폴더가 아님 | 안내 메시지 + 종료 코드 2 |
| 쓴 내용이 OS 캐시에만 남음 | `fsync`로 디스크에 반영 |

### 5.5 실패했을 때의 동작 정리

| 작업 | 실패 시 |
| --- | --- |
| update / delete / 예산 변경 / 카테고리 삭제 / export | **전부 아니면 무**: 원본 그대로 유지 |
| import | **부분 성공**: 문제 있는 행만 건너뛰고, 나머지는 반영하며 사유를 알려 줌 |
| add | 파일 끝에 한 줄을 붙이는 한 번의 쓰기 |



---

## 6. 실행 시연 및 테스트 결과

### 6.1 시연 (명령어 → 기대 결과 → 실제 출력)

출력은 실제 실행 결과(①만 입력을 읽기 쉽게 줄 단위로 정리). `--data-dir`로 빈 폴더를 지정해 처음부터 진행. 보기 편하도록 아래 명령에서는 `--data-dir` 옵션 생략

**① add — 오류 후 재입력, 저장 성공**

기대: 잘못된 날짜·없는 카테고리·0원은 힌트와 함께 재질문, 올바른 값 입력 시 id 출력

```
$ python3 -m budget_app add
날짜(YYYY-MM-DD): 2026-13-40
[오류] 날짜 형식이 올바르지 않습니다 (YYYY-MM-DD).
[힌트] 예: 2026-10-15
날짜(YYYY-MM-DD): 2026-10-15
타입(income/expense): expense
카테고리: foodd
[오류] 등록되지 않은 카테고리입니다: foodd
[힌트] 등록된 카테고리: etc, food, rent, salary, transport / 새로 등록: category add --name foodd
카테고리: food
금액(양수): 0
[오류] 금액은 0보다 큰 양수여야 합니다.
[힌트] 예: 15000
금액(양수): 15000
메모(선택): 점심
태그(쉼표로 구분, 없으면 엔터): meal
[저장 완료] id=TX-000001
```

(위는 입력을 표시하기 쉽게 정리한 것. 실제로는 입력이 같은 줄에 이어짐)

**② list — 최신순**

기대: 날짜 최신순, 열 정렬 상태로 출력

```
$ python3 -m budget_app list --limit 3
TX-000001 | 2026-10-15 | expense | food      |   15000 | 점심  #meal
TX-000002 | 2026-10-14 | income  | salary    | 3000000 |
TX-000004 | 2026-10-12 | expense | transport |   20000 |
```

**③ search**

```
$ python3 -m budget_app search --category food --q 점심
TX-000001 | 2026-10-15 | expense | food | 15000 | 점심  #meal
```

**④ budget set + summary**

기대: 합계, TOP N, 예산 사용률 출력

```
$ python3 -m budget_app budget set --month 2026-10 --amount 500000
[저장 완료] 2026-10 예산 500000원
$ python3 -m budget_app summary --month 2026-10 --top 3
[2026-10 월별 요약]
총 수입: 3000000원
총 지출: 185000원
잔액: 2815000원
예산: 500000원 (사용률 37.0%)

지출 TOP 3
1) rent 150000원
2) transport 20000원
3) food 15000원
```

**⑤ 예산 초과 경고 / 데이터 없는 달**

```
$ python3 -m budget_app budget set --month 2026-10 --amount 100000
$ python3 -m budget_app summary --month 2026-10
...
예산: 100000원 (사용률 185.0%)
[경고] 예산을 85000원 초과했습니다!

$ python3 -m budget_app summary --month 2023-05
[2023-05] 데이터 없음
```

**⑥ update / delete / 없는 id**

기대: 수정·삭제는 성공 메시지, 이미 지운 id는 오류와 종료 코드 1.

```
$ python3 -m budget_app update --id TX-000001 --amount 18000
[수정 완료] id=TX-000001
TX-000001 | 2026-10-15 | expense | food | 18000 | 점심  #meal
$ python3 -m budget_app delete --id TX-000003
[삭제 완료] id=TX-000003
$ python3 -m budget_app delete --id TX-000003
[오류] 존재하지 않는 거래 id 입니다: TX-000003
[힌트] list 명령으로 id 를 확인하세요.        (종료 코드 1)
```

**⑦ 사용 중인 카테고리 삭제 차단**

```
$ python3 -m budget_app category remove --name food
[오류] 'food' 카테고리를 사용하는 거래가 1건 있어 삭제할 수 없습니다.
[힌트] 해당 거래를 update --category 로 다른 카테고리로 바꾸거나 delete 한 뒤 다시 시도하세요.   (종료 코드 1)
```

**⑧ export / import 왕복**

기대: 내보낸 CSV를 그대로 다시 가져오기 가능

```
$ python3 -m budget_app export --out e.csv --month 2026-10
[완료] e.csv (3 records)
$ cat e.csv
date,type,category,amount,memo,tags
2026-10-15,expense,food,18000,점심,meal
2026-10-14,income,salary,3000000,,
2026-10-12,expense,transport,20000,,
$ python3 -m budget_app import --from e.csv
[완료] imported=3, skipped=0
```

**⑨ import 부분 성공** (3줄짜리 CSV: 정상 1건, 날짜 오류 1건, 없는 카테고리 1건)

```
$ python3 -m budget_app import --from mix.csv
  - 3번째 줄: 날짜 형식이 올바르지 않습니다 (YYYY-MM-DD).
  - 4번째 줄: 등록되지 않은 카테고리입니다: nope
[완료] imported=1, skipped=2
```

**⑩ 실제 저장 파일** (`data/`)

```
# transactions.jsonl
{"id":"TX-000001","type":"expense","date":"2026-10-15","amount":18000,"category":"food","memo":"점심","tags":["meal"]}
# categories.jsonl
{"name":"food"}
# budgets.jsonl
{"month":"2026-10","amount":100000}
```
