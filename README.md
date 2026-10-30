# budget_app — 콘솔 가계부

Python 표준 라이브러리만으로 만든 파일 기반 가계부입니다. 수입/지출 추가·수정·삭제, 검색, 월별 요약, 예산 초과 경고, 카테고리 관리, CSV 가져오기/내보내기를 지원합니다.

- Python 3.10 이상, 외부 라이브러리 없음
- 데이터는 JSONL 파일 3개에 영구 저장됩니다.

## 실행 방법

프로젝트 루트(`budget_app/` 폴더가 있는 위치)에서 실행합니다.

```bash
python -m budget_app --help
python -m budget_app <command> [options]
python -m unittest            # 테스트 실행
```

모든 명령은 `--help`를 지원합니다. 옵션 표기는 `--`로 통일했습니다.

공통 옵션 (명령 앞이나 뒤 어디에 써도 됩니다):

| 옵션 | 설명 |
| --- | --- |
| `--data-dir DIR` | 데이터 폴더 (기본 `./data`) |
| `--verbose` | 실행 로그를 stderr로도 출력 |

## 저장 파일 위치와 형식

기본 위치는 `./data/`입니다. 폴더나 파일이 없으면 첫 실행 때 자동으로 만들고 stderr에 `[초기화] ...` 안내를 출력합니다.
`categories.jsonl`이 비어 있으면 기본 카테고리 `food, transport, rent, salary, etc`를 만듭니다.

| 파일 | 한 줄(레코드) 예시 |
| --- | --- |
| `transactions.jsonl` | `{"id":"TX-000001","type":"expense","date":"2024-01-15","amount":15000,"category":"food","memo":"점심","tags":["meal"]}` |
| `categories.jsonl` | `{"name":"food"}` |
| `budgets.jsonl` | `{"month":"2024-01","amount":500000}` |

실행 로그는 `data/budget.log`에 기록됩니다.

## 주요 명령 예시

```text
$ python -m budget_app add                      # 대화형 입력
날짜(YYYY-MM-DD): 2024-01-15
타입(income/expense): expense
카테고리: food
금액(양수): 15000
메모(선택): 점심
태그(쉼표로 구분, 없으면 엔터): meal
[저장 완료] id=TX-000012

$ python -m budget_app list --limit 3           # 최신순, 기본 20건
TX-000012 | 2024-01-15 | expense | food      |   15000 | 점심  #meal
TX-000011 | 2024-01-14 | income  | salary    | 3000000 |
TX-000010 | 2024-01-12 | expense | transport |   20000 |

$ python -m budget_app search --from 2024-01-01 --to 2024-01-31 --category food --type expense --q 점심 --tag meal
$ python -m budget_app budget set --month 2024-01 --amount 500000
[저장 완료] 2024-01 예산 500000원
$ python -m budget_app budget show --month 2024-01

$ python -m budget_app summary --month 2024-01 --top 3
[2024-01 월별 요약]
총 수입: 3000000원
총 지출: 215000원
잔액: 2785000원
예산: 500000원 (사용률 43.0%)

지출 TOP 3
1) rent 150000원
2) food 45000원
3) transport 20000원

$ python -m budget_app category add --name hobby   # --name 을 생략하면 대화형 입력
$ python -m budget_app category list
$ python -m budget_app category remove --name hobby

$ python -m budget_app update --id TX-000012 --amount 18000 --memo "점심(수정)"
$ python -m budget_app delete --id TX-000012

$ python -m budget_app export --out export.csv --month 2024-01
[완료] export.csv (12 records)
$ python -m budget_app import --from import.csv
[완료] imported=5, skipped=0
```

| 명령 | 옵션 |
| --- | --- |
| `add` | 대화형 (옵션 없음) |
| `list` | `--limit N` (기본 20) |
| `search` | `--from --to --category --type --q --tag --limit` |
| `summary` | `--month YYYY-MM` (필수), `--top N` (기본 3) |
| `budget set` / `budget show` | `--month`, `--amount` (set만) |
| `category add` / `list` / `remove` | `--name` |
| `update` | `--id` (필수) + `--date --type --category --amount --memo --tags` 중 바꿀 항목 |
| `delete` | `--id` (필수) |
| `import` | `--from <csv>` |
| `export` | `--out <csv>` + (`--month` 또는 `--from/--to`), 기간 조건 필수 |

## 동작 정책 (고정한 선택)

- **update**: 옵션 방식입니다. 지정한 항목만 바꾸고, `--memo ""`, `--tags ""`는 해당 항목을 비웁니다.
- **카테고리 삭제**: 그 카테고리를 쓰는 거래가 있으면 삭제를 거부하고 건수와 해결 방법을 안내합니다.
- **초기 카테고리**: 비어 있으면 기본 카테고리를 자동 생성합니다.
- **최신순**: `(date, id)` 내림차순입니다. 날짜가 같으면 나중에 만든 거래가 먼저 나옵니다.
- **id 재사용**: 새 id는 현재 파일에서 가장 큰 번호 + 1입니다. 가장 마지막 거래를 삭제하면 그 번호가 다시 쓰일 수 있습니다.
- **search**: `--limit`이 없으면 조건에 맞는 거래 전부를 정렬해 출력합니다. 이때는 매칭된 건수만큼 메모리를 씁니다.
- **import**: 오류가 있는 행은 건너뛰고 `skipped`로 셉니다. 사유는 줄 번호와 함께 stderr에 출력합니다. 등록되지 않은 카테고리의 행도 건너뜁니다(자동 생성하지 않음). 같은 파일을 두 번 가져오면 중복 등록됩니다.
- **export**: 저장된 순서대로 씁니다.
- **금액**: 양의 정수(원)입니다.

## import / export CSV 스키마

UTF-8, 첫 줄은 헤더입니다. 컬럼 순서는 자유이고 `memo`, `tags` 컬럼은 없어도 됩니다. (import는 BOM이 있어도 읽습니다.)

| column | required | 설명 |
| --- | --- | --- |
| date | Y | `YYYY-MM-DD` |
| type | Y | `income` / `expense` |
| category | Y | 등록된 카테고리 |
| amount | Y | 양수 정수 |
| memo | N | 문자열 |
| tags | N | 쉼표(`,`) 구분 문자열. 쉼표가 들어 있으므로 CSV에서는 `"a,b"`처럼 따옴표로 감싸집니다. |

```csv
date,type,category,amount,memo,tags
2024-01-15,expense,food,15000,점심,meal
2024-01-14,income,salary,3000000,,
2024-01-12,expense,transport,20000,버스,"commute,daily"
```

## 오류 처리와 종료 코드

오류는 스택트레이스 없이 원인과 해결 힌트로 출력합니다. 예상하지 못한 오류의 상세 내용은 `data/budget.log`에만 남습니다.

```text
[오류] 날짜 형식이 올바르지 않습니다 (YYYY-MM-DD).
[힌트] 예: 2024-01-15
```

| 종료 코드 | 의미 |
| --- | --- |
| 0 | 정상 |
| 1 | 입력 오류, 없는 id/카테고리, 사용 중인 카테고리 삭제 등 |
| 2 | 저장 파일/경로 오류, 명령행 사용법 오류 |
| 70 | 예기치 못한 내부 오류 |
| 130 | 입력 취소 (Ctrl+C, 입력 도중 EOF) |

## 구조

```
budget_app/
├── __main__.py     python -m budget_app 진입점
├── cli.py          argparse, 대화형 입력, 출력, 종료 코드
├── services.py     비즈니스 규칙 (카테고리 확인, 검색, 요약, CSV 흐름)
├── storage.py      JSONL 저장소: 스트리밍 읽기, append, 원자적 재작성
├── models.py       dataclass, 입력 검증, 예외 계층
├── csv_io.py       CSV 스키마와 읽기/쓰기
├── formatters.py   출력 포맷 (한글 폭을 고려한 표 정렬)
└── decorators.py   handle_errors / log_call / timed
```

의존 방향은 `cli → services → storage → models`입니다. 아래 계층은 위 계층을 import하지 않습니다.

- **제너레이터 스트리밍**: `JsonlFile.stream()`은 파일을 한 줄씩 읽어 `yield`합니다. 파일이 아무리 커도 한 번에 메모리에 올리지 않습니다. 최신순 정렬이 필요한 `list`/`search --limit N`은 스트림을 `heapq.nlargest`에 넘겨서 메모리를 N건으로 묶습니다. `summary`와 `export`도 스트림을 한 번만 순회합니다.
- **원자적 쓰기**: update/delete/예산 변경/카테고리 삭제는 같은 폴더의 임시 파일에 전부 쓰고 `fsync`한 뒤 `os.replace`로 교체합니다. 도중에 실패해도 원본 파일은 그대로입니다.
- **데코레이터**:
  - `@handle_errors` — 모든 예외를 메시지와 종료 코드로 바꿉니다. 명령 실행 진입점 `run()`에 적용했습니다.
  - `@log_call` — 서비스의 쓰기 작업(add/update/delete 등)의 호출과 결과를 `budget.log`에 기록합니다.
  - `@timed` — search, summary, import, export의 실행 시간을 기록합니다.
- **타입 힌트**: 모든 함수에 인자·반환 타입을 붙였습니다. 제너레이터는 `Iterator[Transaction]`으로 표기해 "한 건씩 흘려보낸다"는 계약이 시그니처에 드러납니다. `TxType = Literal["income", "expense"]`로 허용 값을 타입에 담았고, `JsonlFile[T]`는 제네릭으로 거래/카테고리/예산 저장소가 같은 구현을 공유합니다.
- **데이터 모델**: `Transaction`, `Budget`, `SearchCriteria`, `MonthlySummary`, `ImportResult`는 `frozen=True` dataclass입니다. 수정은 `dataclasses.replace`로 새 객체를 만듭니다.

## 보너스 구현 여부

- 출력 테이블 정렬: 구현 (`formatters.py`, 외부 라이브러리 없음)
- 저장 원자성 강화: 구현 (임시 파일 + `os.replace`)
- 백업, 반복 내역: 미구현
