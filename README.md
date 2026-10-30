# 콘솔 가계부 `budget_app` 설명 문서

> 평가 때 위에서 아래로 따라가며 설명하기 위한 문서입니다. 파일명과 줄 번호는 현재 코드 기준이고, 실행 결과는 실제로 돌려서 얻은 출력입니다.

---

## 1. 프로젝트 개요

### 무엇을 만들었나

Python 표준 라이브러리만 사용한 **콘솔 가계부**
 터미널에서 명령어로 수입/지출을 기록하고, 조회·검색·수정·삭제하고, 월별 요약과 예산 초과 경고를 볼 수 있음. 데이터는 파일에 저장되어서 프로그램을 껐다 켜도 남음

```bash
python3 -m budget_app add        # 대화형으로 거래 추가
python3 -m budget_app list       # 최신순 목록
python3 -m budget_app summary --month 2024-01
```


---

## 2. 요구사항과 구현 결과

### 필수 기능 10가지

| # | 기능 | 명령 | 진입 함수 (cli.py) | 핵심 로직 위치 | 검증 |
| --- | --- | --- | --- | --- | --- |
| 1 | 거래 추가 | `add` | `cmd_add` :50 | `TransactionService.add` services.py:82 | 7장 시연 ①, test_service `TransactionTests` |
| 2 | 거래 목록 | `list --limit N` | `cmd_list` :73 | `list_recent` services.py:133 → `search` :160 | 시연 ②, 30만 건 측정 |
| 3 | 거래 검색 | `search --from --to --category --type --q --tag` | `cmd_search` :78 | `make_criteria` :136, `SearchCriteria.matches` models.py:181 | 시연 ③, test_service `SearchTests` |
| 4 | 월별 요약 | `summary --month --top` | `cmd_summary` :87 | `ReportService.monthly_summary` services.py:192 | 시연 ④, test_service `SummaryTests` |
| 5 | 예산 설정/조회 | `budget set`, `budget show` | `cmd_budget_set` :93 | `BudgetService.set` services.py:177 → `BudgetStore` storage.py:186 | 시연 ④⑤ |
| 6 | 카테고리 관리 | `category add/list/remove` | `cmd_category_*` :109~128 | `CategoryService` services.py:36 | 시연 ⑦, test_service `CategoryTests` |
| 7 | 거래 수정 | `update --id ...` | `cmd_update` :134 | `TransactionService.update` services.py:97 → `TransactionRepository.update` storage.py:123 | 시연 ⑥ |
| 8 | 거래 삭제 | `delete --id` | `cmd_delete` :144 | `TransactionRepository.delete` storage.py:131 | 시연 ⑥ |
| 9 | 가져오기 | `import --from` | `cmd_import` :150 | `CsvService.import_` services.py:256 + `csv_io.read_rows` :44 | 시연 ⑧⑨ |
| 10 | 내보내기 | `export --out --month` | `cmd_export` :158 | `CsvService.export` services.py:237 + `csv_io.write_transactions` :17 | 시연 ⑧ |

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
| 데코레이터 1개 이상 적용 | 3개 구현, 실제 적용 | decorators.py |
| 스택트레이스 금지, 종료 코드 | `handle_errors` | decorators.py:73 |
| 모듈 3개 이상 | 8개 | `budget_app/` |
| 표준 라이브러리만 사용 | 외부 import 없음 | 전체 |
| README | 실행 방법·저장 파일·명령 예시·CSV 스키마 | README.md |

### 설계 선택 (평가 때 "왜?"라고 물을 만한 곳)

| 선택 | 이유 |
| --- | --- |
| 저장 포맷은 **JSONL** | 한 줄이 한 레코드라 한 줄씩 읽는 스트리밍에 맞고, tags를 리스트 그대로 저장할 수 있다 (9번 비교는 4장) |
| update는 **옵션 방식** | `update --id X --amount 5000`처럼 바꿀 항목만 적을 수 있고 테스트하기 쉽다 |
| 초기 카테고리는 **자동 생성** | 첫 실행부터 바로 `add`를 쓸 수 있다 |
| 사용 중인 카테고리는 **삭제 차단** | 거래가 존재하지 않는 카테고리를 가리키는 상황을 원천 차단하는 가장 단순한 방법 |
| 최신순 기준은 `(날짜, id)` 내림차순 | 날짜가 같으면 나중에 만든 거래가 먼저 나온다 |

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
├── tests/              unittest 57개
├── data/               실행 시 생성되는 저장 폴더 (git 제외)
│   ├── transactions.jsonl
│   ├── categories.jsonl
│   ├── budgets.jsonl
│   └── budget.log
├── README.md
└── EXPLAIN.md
```

### 모듈 관계

호출은 위에서 아래로만 흐르고, **아래 계층은 위 계층을 import하지 않습니다.**

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
   │   storage.py    │  파일에서 읽고 쓰기만 한다 (규칙은 모른다)
   └───────┬─────────┘
           ▼
     data/*.jsonl

 models.py : 모든 계층이 같이 쓰는 데이터 구조 + 검증 + 예외
 decorators.py : 서비스/진입점에 덧붙는 공통 기능
```

### 클래스의 책임 경계

| 계층 | 클래스 | 맡은 일 | 모르는 것 |
| --- | --- | --- | --- |
| storage | `JsonlFile[T]` | 한 줄씩 읽기, append, 안전하게 다시 쓰기 | 거래가 무엇인지 |
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

**예시**: "사용 중인 카테고리는 삭제하지 못한다"는 규칙은 `CategoryService.remove`(services.py:62)에만 있습니다. 저장소는 그냥 지우는 일만 하고, CLI는 서비스가 던진 예외를 메시지로 보여줄 뿐입니다. 규칙을 바꾸고 싶을 때 고칠 곳이 한 군데입니다.

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
| `transactions.jsonl` | `{"id":"TX-000001","type":"expense","date":"2024-01-15","amount":18000,"category":"food","memo":"점심","tags":["meal"]}` |
| `categories.jsonl` | `{"name":"food"}` |
| `budgets.jsonl` | `{"month":"2024-01","amount":100000}` |

---

## 4. 핵심 기술 설명

### 4.1 Generator (제너레이터)

**한 줄 정의**: 값을 `return`으로 한꺼번에 주지 않고 `yield`로 **하나씩 건네주는** 함수입니다. 뷔페처럼 한 접시씩 가져옵니다.

**내 코드** — `storage.py:46`

```python
def stream(self) -> Iterator[T]:
    with self.path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            ...
            yield item        # 한 건을 돌려주고, 다음 요청이 올 때까지 멈춘다
```

**왜 썼나**: `list`로 전부 읽으면 거래 수만큼 메모리를 씁니다. 제너레이터는 필요한 만큼만 읽습니다.

**최신순이 문제였다**: 파일에는 오래된 거래가 먼저 쌓이는데, 출력은 최신순이어야 합니다. 그래서 스트림을 `heapq.nlargest(limit, ...)`에 넘깁니다(`services.py:169`). 이 함수는 "지금까지 본 것 중 가장 큰 limit개"만 들고 있으므로 파일이 아무리 커도 메모리는 limit 건수만큼입니다.

**측정 결과** (35MB, 30만 건 파일)

| 방식 | 최대 메모리 |
| --- | --- |
| 이 프로그램의 `list --limit 3` | 약 20MB |
| `summary --month 2024-05` | 약 21MB |
| 비교: 파일 전체를 리스트로 읽기 | 약 299MB |

`list`, `search`, `summary`, `export`가 모두 같은 `stream()`을 한 번 훑는 방식으로 동작합니다.

**한계**: `search`를 `--limit` 없이 쓰면 조건에 맞는 거래 전부를 정렬해야 해서 그 건수만큼 메모리를 씁니다.

### 4.2 Decorator (데코레이터)

**한 줄 정의**: 함수를 감싸서 **원래 코드를 건드리지 않고** 기능을 덧붙이는 문법입니다. 선물 포장지처럼 겉에 하나 더 씌웁니다.

**내 코드** — `decorators.py`에 3개

| 데코레이터 | 하는 일 | 붙인 곳 |
| --- | --- | --- |
| `@handle_errors` (:73) | 예외를 `[오류]/[힌트]` 메시지와 종료 코드로 바꿈 | `run()` (cli.py:285) |
| `@log_call` (:34) | 호출·성공·실패를 `budget.log`에 기록 | `add`/`update`/`delete`/`set`/`remove`/`import_`/`export` |
| `@timed` (:52) | 실행 시간을 `budget.log`에 기록 | `search`, `monthly_summary`, `import_`, `export` |

```python
def log_call(func):
    @functools.wraps(func)                 # 원래 함수의 이름/설명을 유지
    def wrapper(*args, **kwargs):
        logger.info("call %s(...)", func.__qualname__)
        try:
            result = func(*args, **kwargs)  # 원래 함수 실행
        except Exception:
            logger.warning("fail ...")
            raise                           # 예외는 그대로 다시 던진다
        logger.info("ok   %s", ...)
        return result
    return wrapper
```

**왜 썼나**: 서비스 메서드마다 로그와 try/except를 쓰면 중복이 생기고 본래 로직이 묻힙니다. 데코레이터를 쓰면 서비스 코드는 업무 규칙만 남습니다.

**실제 로그** (`data/budget.log`)

```
INFO call TransactionService.add(date='2024-01-01', type='expense', category='food', amount=100, ...)
INFO ok   TransactionService.add
INFO time ReportService.monthly_summary 0.1ms
WARNING fail TransactionService.delete: NotFoundError: 존재하지 않는 거래 id 입니다: TX-999
```

> 참고: 코드에 보이는 `ParamSpec`, `Callable[P, R]`은 "감싼 함수의 인자 모양을 그대로 유지한다"는 타입 표기일 뿐이고, 실행 동작에는 영향이 없습니다.

### 4.3 Type Hint (타입 힌트)

**한 줄 정의**: 함수의 인자와 반환값이 어떤 타입인지 **코드에 미리 적어 두는** 표기입니다. 실행을 막지는 않지만 읽는 사람과 도구에게 약속이 됩니다.

**내 코드에서 눈에 띄는 것**

| 표기 | 위치 | 의미 |
| --- | --- | --- |
| `TxType = Literal["income", "expense"]` | models.py:10 | 거래 타입은 이 두 문자열만 허용된다는 약속 |
| `def stream(self) -> Iterator[T]` | storage.py:46 | "한 건씩 흘려보낸다"는 사실이 시그니처에 드러남 |
| `def get(self, tx_id: str) -> Transaction \| None` | storage.py:120 | 결과가 **없을 수도 있다**고 호출하는 쪽에 알림 |
| `class JsonlFile(Generic[T])` | storage.py:33 | `T`는 자리표시자. 거래/카테고리/예산 저장소가 같은 코드를 공유 |
| `def parse_amount(value: str \| int) -> int` | models.py:75 | 문자열이나 정수를 받아 항상 양의 정수를 돌려줌 |

**얻는 이점**: 함수 정의만 읽어도 무엇을 넣고 무엇이 나오는지 압니다. 에디터가 오타나 타입 불일치를 미리 알려 줍니다.

**주의**: 타입을 자동 검사하는 도구(mypy)는 설치하지 않아 돌려 보지 않았습니다. 타입 힌트는 문서화와 에디터 지원 용도로 썼습니다.

### 4.4 Dataclass

**한 줄 정의**: 데이터를 담는 클래스를 `__init__` 등을 직접 쓰지 않고 선언만으로 만드는 문법입니다.

**내 코드** — `models.py:131`

```python
@dataclass(frozen=True)
class Transaction:
    id: str
    type: TxType
    date: str
    amount: int
    category: str
    memo: str = ""
    tags: tuple[str, ...] = ()
```

- `frozen=True`: 만든 뒤 값을 바꿀 수 없습니다. 수정할 때는 `dataclasses.replace()`로 **새 객체**를 만들어서(`services.py` update) 의도치 않은 변경을 막습니다.
- 같은 방식으로 `Budget`, `SearchCriteria`, `MonthlySummary`, `ImportResult`를 정의했습니다.
- `to_dict()` / `from_dict()`로 파일의 JSON 한 줄과 객체를 오갑니다.

### 4.5 파일 I/O

| 동작 | 방법 | 위치 |
| --- | --- | --- |
| 읽기 | `open()`을 열고 한 줄씩 순회하며 `yield` | storage.py:46 |
| 추가 | `"a"` 모드로 열어 한 줄 쓰고 `flush` + `fsync` | storage.py:69 |
| 수정·삭제 | 임시 파일에 전부 쓰고 `os.replace`로 교체 | storage.py:78 |
| 인코딩 | 항상 UTF-8, `ensure_ascii=False`로 한글 그대로 저장 | storage.py |

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

UTF-8, 첫 줄은 헤더입니다. 읽을 때는 BOM이 있어도 받고, 컬럼 순서는 상관없습니다. 필수 컬럼이 빠지면 파일 전체를 거부합니다.

---

## 5. 핵심 기능의 코드 실행 흐름

공통 진입부터 보겠습니다.

```
python3 -m budget_app <명령>
  → __main__.py → cli.main()                    cli.py:296
  → build_parser().parse_args()                 명령/옵션 해석
  → run(args)  ← @handle_errors로 감싸져 있음      cli.py:286
        Storage(data_dir).initialize()          폴더/파일 없으면 생성
        로그 파일 설정
        args.func(args, AppContext(storage))    선택된 cmd_* 실행
  → 반환값(종료 코드)으로 프로그램 종료
```

### 5.1 `add` — 입력 → 검증 → 서비스 → 저장소 → 출력

```
① 입력      cli.cmd_add (cli.py:50)
              _prompt("날짜: ", parse_date)       ┐ 검증 실패 시
              _prompt("타입: ", parse_type)       │ [오류]/[힌트] 출력하고
              _prompt("카테고리: ", require)       │ 같은 항목을 다시 묻는다
              _prompt("금액: ", parse_amount)     ┘
② 검증      models.parse_* (models.py:53~110)
              날짜 형식, 양수 정수, income/expense 확인
            CategoryService.require (services.py:44)
              등록된 카테고리인지 확인, 아니면 목록과 등록 방법을 힌트로 안내
③ 서비스    TransactionService.add (services.py:82)
              다시 한 번 검증 후 Transaction 객체 생성
④ 저장소    TransactionRepository.next_id (storage.py:112)  → TX-000012
            JsonlFile.append_many (storage.py:69)           → 파일 끝에 한 줄
⑤ 출력      "[저장 완료] id=TX-000012"
```

검증을 CLI와 서비스에서 두 번 하는 이유는 역할이 다르기 때문입니다. CLI는 "틀리면 바로 다시 묻기"를 위해, 서비스는 CLI가 아닌 경로(CSV import 등)로 들어온 값도 막기 위해서입니다.

### 5.2 `list` / `search` — 스트리밍 + 최신순

```
cmd_list / cmd_search
  → make_criteria  (조건을 SearchCriteria로 묶고 날짜 형식 검증)  services.py:136
  → TransactionService.search (@timed)                            services.py:160
        stream_matching  = (tx for tx in stream_all() if 조건에 맞음)   ← 제너레이터 체인
        heapq.nlargest(limit, matches, key=(date, id))                 ← limit건만 유지
  → format_transactions  (열 너비를 맞춰 정렬, 한글은 2칸으로 계산)
  → 출력
```

### 5.3 `summary` — 한 번 훑으면서 집계

```
cmd_summary → ReportService.monthly_summary (@timed)            services.py:192
   stream_all()을 한 번 돌면서:
     해당 월이 아니면 건너뜀
     income이면 총수입에 더함 / expense면 총지출 + 카테고리별 합계(Counter)
   TOP N = 카테고리별 합계를 큰 순으로 N개
   예산이 있으면 사용률 = 총지출 / 예산 × 100, 초과 여부 계산
   거래가 0건이면 "데이터 없음"
 → format_summary → 출력
```

### 5.4 `update` / `delete` — 전부 아니면 무

```
cmd_update → TransactionService.update (@log_call)              services.py:97
   바꿀 항목만 검증 (하나도 없으면 오류)
   repo.get(id) 로 기존 거래 확인 (없으면 NotFoundError)
   dataclasses.replace(old, **changes) 로 새 객체 생성
   repo.update → JsonlFile.rewrite                              storage.py:78
        ① 같은 폴더에 임시 파일 생성
        ② 원본을 한 줄씩 읽으며, 대상 id만 새 내용으로 바꿔 임시 파일에 씀
        ③ flush + fsync (디스크에 확실히 기록)
        ④ os.replace(임시, 원본)   ← 이름만 바꾸는 한 번의 동작이라 중간 상태가 없다
        ⑤ 예외가 나면 임시 파일 삭제, 원본은 그대로
```

`delete`도 같은 `rewrite`를 쓰되 대상 id를 건너뛰고 씁니다.

### 5.5 `import` — 부분 성공

```
cmd_import → CsvService.import_ (@log_call @timed)              services.py:256
   csv_io.read_rows: 헤더 검증 (필수 컬럼이 없으면 파일 전체 거부)
   행마다 날짜/타입/카테고리/금액 검증
        통과 → valid 목록에 모음
        실패 → errors 목록에 "N번째 줄: 사유" 기록하고 건너뜀
   통과한 행만 새 id를 붙여 한 번에 append_many
   → "[완료] imported=N, skipped=M" + 오류 사유 출력
```

---

## 6. 예외 처리와 데이터 안전성

### 6.1 예외 구조

`models.py:19`의 `BudgetAppError`가 모든 앱 예외의 부모이고, **원인(message)** 과 **해결 힌트(hint)** 를 항상 가집니다.

```
BudgetAppError
├── ValidationError     입력값이 규칙에 안 맞음 (날짜/금액/타입/기간)
├── NotFoundError       없는 id, 등록되지 않은 카테고리
├── DuplicateError      이미 있는 카테고리
├── CategoryInUseError  거래가 쓰는 카테고리 삭제 시도
└── StorageError        저장 파일이 손상되었거나 쓸 수 없음
```

`@handle_errors`(decorators.py:73)가 이 예외를 잡아 다음 형태로 출력합니다. **스택트레이스는 화면에 나오지 않습니다.**

```
[오류] 날짜 형식이 올바르지 않습니다 (YYYY-MM-DD).
[힌트] 예: 2024-01-15
```

### 6.2 종료 코드

| 코드 | 상황 |
| --- | --- |
| 0 | 정상 |
| 1 | 입력 오류, 없는 id/카테고리, 사용 중인 카테고리 삭제 |
| 2 | 저장 파일/경로 오류, 명령 사용법 오류 |
| 70 | 예상하지 못한 오류 (상세는 `budget.log`에만 기록) |
| 130 | 입력 취소 (Ctrl+C, 입력 도중 EOF) |

### 6.3 비정상 입력 처리

| 입력 | 결과 |
| --- | --- |
| `2024-13-40` (잘못된 날짜) | 오류 + 힌트, `add`에서는 같은 항목 재입력 |
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

### 6.4 파일 손상 방지

| 위험 | 대응 |
| --- | --- |
| 수정/삭제 도중 프로그램이 멈춤 | 원본은 건드리지 않고 임시 파일에 쓴 뒤 `os.replace`로 교체. 실패하면 임시 파일만 삭제 |
| 교체 직전 디스크 오류 | 같은 방식으로 원본 유지 (테스트에서 `os.replace`를 강제로 실패시켜 확인) |
| 파일 내용이 깨져 있음 | `N번째 줄을 읽을 수 없습니다`와 해결 힌트를 보여주고 종료 (조용히 무시하지 않음) |
| 쓰기 권한 없음, 데이터 경로가 폴더가 아님 | 안내 메시지 + 종료 코드 2 |
| 쓴 내용이 OS 캐시에만 남음 | `fsync`로 디스크에 반영 |

### 6.5 실패했을 때의 동작 정리

| 작업 | 실패 시 |
| --- | --- |
| update / delete / 예산 변경 / 카테고리 삭제 / export | **전부 아니면 무**: 원본 그대로 유지 |
| import | **부분 성공**: 문제 있는 행만 건너뛰고, 나머지는 반영하며 사유를 알려 줌 |
| add | 파일 끝에 한 줄을 붙이는 한 번의 쓰기 |



---

## 7. 실행 시연 및 테스트 결과

### 7.1 시연 (명령어 → 기대 결과 → 실제 출력)

출력은 실제 실행 결과입니다(①만 입력을 읽기 쉽게 줄 단위로 정리했습니다). `--data-dir`로 빈 폴더를 지정해 처음부터 진행했고, 보기 편하도록 아래 명령에서는 `--data-dir` 옵션을 생략했습니다.

**① add — 오류 후 재입력, 저장 성공**

기대: 잘못된 날짜·없는 카테고리·0원은 힌트와 함께 다시 묻고, 올바른 값이 들어오면 id를 출력한다.

```
$ python3 -m budget_app add
날짜(YYYY-MM-DD): 2024-13-40
[오류] 날짜 형식이 올바르지 않습니다 (YYYY-MM-DD).
[힌트] 예: 2024-01-15
날짜(YYYY-MM-DD): 2024-01-15
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

(위는 입력을 표시하기 쉽게 정리한 것입니다. 실제로는 입력이 같은 줄에 이어집니다.)

**② list — 최신순**

기대: 날짜가 최신인 순으로, 열이 정렬되어 출력된다.

```
$ python3 -m budget_app list --limit 3
TX-000001 | 2024-01-15 | expense | food      |   15000 | 점심  #meal
TX-000002 | 2024-01-14 | income  | salary    | 3000000 |
TX-000004 | 2024-01-12 | expense | transport |   20000 |
```

**③ search**

```
$ python3 -m budget_app search --category food --q 점심
TX-000001 | 2024-01-15 | expense | food | 15000 | 점심  #meal
```

**④ budget set + summary**

기대: 합계와 TOP N, 예산 사용률이 나온다.

```
$ python3 -m budget_app budget set --month 2024-01 --amount 500000
[저장 완료] 2024-01 예산 500000원
$ python3 -m budget_app summary --month 2024-01 --top 3
[2024-01 월별 요약]
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
$ python3 -m budget_app budget set --month 2024-01 --amount 100000
$ python3 -m budget_app summary --month 2024-01
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
TX-000001 | 2024-01-15 | expense | food | 18000 | 점심  #meal
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

기대: 내보낸 CSV를 그대로 다시 가져올 수 있다.

```
$ python3 -m budget_app export --out e.csv --month 2024-01
[완료] e.csv (3 records)
$ cat e.csv
date,type,category,amount,memo,tags
2024-01-15,expense,food,18000,점심,meal
2024-01-14,income,salary,3000000,,
2024-01-12,expense,transport,20000,,
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
{"id":"TX-000001","type":"expense","date":"2024-01-15","amount":18000,"category":"food","memo":"점심","tags":["meal"]}
# categories.jsonl
{"name":"food"}
# budgets.jsonl
{"month":"2024-01","amount":100000}
```
