# pne_scheduler — 프로젝트 구조 & 코드 규칙

> 헤매지 않기 위한 **디렉터리 지도**와 **작성 규칙**.  
> 로드맵·정책·스펙은 각각 [`ROADMAP.md`](ROADMAP.md), [`LAB_DATA_POLICY.md`](LAB_DATA_POLICY.md), [`docs/`](../docs/) 를 본다.

---

## 코드 규칙

### 1. 새 코드 전에 반드시 검색

새 파일·함수·클래스를 만들기 **전에** 저장소 전체에서 유사 기능을 grep한다.

```powershell
# 예: 코퍼스 분석 도구를 추가하려면
rg "corpus|zip.*scan|analyze_pne" pne_scheduler/
```

이미 있는 것을 찾았으면 **확장**한다. 복제하지 않는다.

### 2. 대체했으면 구버전 삭제

기능을 새 구현으로 옮겼다면 **구버전 파일·함수를 즉시 삭제**한다.

- 주석 처리로 남기지 않는다 (git이 히스토리를 보관한다).
- `deprecated`, `legacy`, `old_*` 이름으로 방치하지 않는다.
- `_` 접두 일회성 스크립트도 목적이 끝나면 삭제 대상이다.

**현재 정리 대상 예시** (grep 참조 0건, [`ROADMAP.md`](ROADMAP.md) dead-code 감사 참고):

| 삭제·통합 대상 | 대체·유지 |
|----------------|-----------|
| `tools/analyze_pne_zip_corpus.py`, `tools/_parse_sch_struct.py` 등 `_` 도구 | `tools/analyze_pne_unit_corpus.py` |
| `io/reader.py` (ASSB thin wrapper) | `io/sch_parser.py` |
| `schema/fields.py` 의 I/O 오프셋 상수 | `schema/ensol_v612.py` |
| `vendor/.../project_archive/` | 참조용 `vendor/ensol_sch_maker_ref/battery_scheduler/` 만 |

### 3. 하위 호환·fallback 금지

다음 패턴은 **금지**:

- 구 API를 감싸는 wrapper (`def old_read(): return new_read()`)
- “혹시 몰라” 이중 경로 (`try A except: B`)
- 사용되지 않는 export를 `__init__.py`에 남겨 두기

호출부를 한 번에 고친다. 테스트가 깨지면 테스트도 같이 고친다.

### 4. 공통 로직 위치 (이 프로젝트)

이 패키지에는 `src/utils/` 가 **없다**. 도메인별 패키지에 둔다.

| 필요한 것 | 넣을 곳 | 새 파일 만들지 말 것 |
|-----------|---------|---------------------|
| SCH 바이너리 읽기/쓰기 | `io/` | `io/utils.py`, `helpers/` |
| 스텝 오프셋·버전 상수 | `schema/` | 루트 `constants.py` |
| C-rate ↔ 전류 | `engine/c_rate.py` | |
| FP / L-level / 용량 추론 | `stack/` | |
| 파일명 실험 분류 | `classify/` | |
| 프로토콜 추론 | `protocol/` | |
| 장비 정격·레지스트리 | `schema/equipment*.py` + `planning/*.json` | |
| 실험 모듈 (cycle, FM, RPT…) | `modules/` | |
| 오프라인 분석 CLI | `tools/` | `tools/_*.py` (일회성) |
| Gate B 검증·intake | `validate/` | |

**원칙:** “어디에나 쓰는 유틸”이 생기면, **가장 가까운 도메인 모듈**에 함수를 추가한다. 새 top-level `utils.py` / `helpers.py` / `common.py` 는 만들지 않는다.

### 5. 진입점은 하나로 유지

| 용도 | 진입점 |
|------|--------|
| 패키지 CLI | `python -m pne_scheduler` → [`__main__.py`](../__main__.py) |
| GUI 런처 | 루트 `run_pne_scheduler_*.py` (tkinter 창만 열고 `ui/` 호출) |
| 오프라인 분석 | `python -m pne_scheduler.tools.<script>` 또는 `tools/*.py` 직접 실행 |
| 테스트 | `pytest` → [`tests/`](../tests/) |

동일 CLI를 `run_*.py` 와 `tools/` 양쪽에 중복 정의하지 않는다.

---

## 워크스페이스 맥락

`C:\Users\LGES\Cursor` 레포에는 형제 프로젝트가 있다.

| 경로 | 역할 |
|------|------|
| **`pne_scheduler/`** | 이 문서의 대상. PNE `.sch` 스케줄 빌더·뷰어·재개 |
| `cyclediag/` | 사이클 데이터 진단·피크 추적 (별도 패키지) |
| `example/`, `_vendor/` | 외부 참조·샘플 (pne_scheduler와 직접 import 하지 않음) |

**pne_scheduler 작업 시 `cyclediag/` 코드를 import 하지 않는다.**

---

## 디렉터리 지도

```
pne_scheduler/
├── __main__.py          # CLI (build, view, compare, patch-sch, resume, …)
├── run_pne_scheduler*.py # GUI/CLI 런처 (얇은 진입점)
│
├── classify/            # 파일명 → 실험 유형 (FM, capacheck, cycle, …)
├── protocol/            # 스케줄 내용 → 프로토콜 추론
├── stack/               # FP, L-level, Q_nom, C-rate, silicon 코드
├── ir/                  # ScheduleProject, StepIntent, CellProfile (중간 표현)
├── modules/             # 실험 모듈 → StepIntent 시퀀스 확장
├── engine/              # StepIntent → 바이너리 스텝 레코드 컴파일
├── io/                  # .sch 읽기/쓰기, 레이아웃 감지, 템플릿 패치
├── schema/              # 바이너리 오프셋, enum, 장비·코퍼스 메타
├── edit/                # .schproj 벌크 편집 로직
├── resume/              # 중단 실험 재개 (checkpoint, splice)
├── ui/                  # tkinter GUI (viewer, editor, flow, resume wizard)
├── validate/            # Gate B intake, ASSB 파서 diff, roundtrip
├── tools/               # 오프라인 분석·리포트 CLI (코퍼스, compare, fixture)
├── vendor/              # 외부 참조 코드 (ASSB parser, Ensol sch_maker) — 수정 최소화
│
├── planning/            # 정책, 로드맵, 장비 레지스트리 JSON, 코퍼스 리포트
├── docs/                # 사용자·검증 가이드 (RESUME, PROTOCOL, Gate B, …)
├── example/             # .schproj, golden fixture, 분석 출력 샘플
└── tests/               # pytest (golden, 단위, CLI 안전성)
```

### 데이터 흐름 (읽기)

```
.sch 파일
  → io/layout.py        (payload offset, step size 감지)
  → io/sch_parser.py    (ScheduleDocument — UI·테스트·검증의 단일 파서)
  → classify/ + stack/ + protocol/  (파일명·스텝에서 메타 추론)
  → ui/ 또는 tools/     (표시·리포트)
```

### 데이터 흐름 (쓰기)

```
.schproj (ir/project.py)
  → modules/*           (실험 블록 → StepIntent[])
  → engine/compiler.py  (StepIntent → bytes, ensol_v612 오프셋)
  → io/template_writer.py   (템플릿 보존 패치 — 분석·재개용, 권장)
  → io/writer.py            (실험적 전체 빌드 — equipment 미검증)
```

---

## 패키지별 상세

### `classify/`

- **`schedule_filename.py`** — `.sch` 파일명 규칙으로 `formation`, `capacheck`, `cycle`, `hppc`, `doe` 등 분류.
- 새 카테고리는 여기 규칙만 추가. 별도 classifier 파일 만들지 않는다.

### `protocol/`

- 스케줄 스텝 패턴에서 프로토콜 라벨 추론 (`infer.py`, `defaults.py`).
- 파일명 분류(`classify/`)와 역할이 겹치지 않게: **파일명 → classify**, **스텝 내용 → protocol**.

### `stack/`

- 셀 geometry: footprint, mono/multi, L-level, nominal capacity.
- `infer.py`가 진입점. C-rate 계산은 `engine/c_rate.py`에 둔다 (stack에 중복 정의 금지).

### `ir/`

- **`project.py`** — `.schproj` JSON 모델, 모듈 그래프, `expand_steps()`.
- **`step_intent.py`** — 컴파일 전 의도 단위 (charge, rest, loop, end, …).
- **`cell_profile.py`** — Q_nom, 전압 한계 등 셀 파라미터.

### `modules/`

- ASSB 실험 유형별 블록: `formation`, `capacheck`, `cycle_life`, `rpt`, `hppc`, `dcir`, …
- `base.py`의 `register_module` / `expand_module`만 통해 등록. 모듈별 독자 IR 확장 금지.

### `engine/`

- **`compiler.py`** — `StepIntent[]` → 612B 스텝 레코드 (`schema/ensol_v612.py` 오프셋 사용).
- **`c_rate.py`** — C-rate ↔ mA 변환.

### `io/` — SCH I/O 단일 허브

| 파일 | 역할 | 상태 |
|------|------|------|
| **`sch_parser.py`** | 메인 파서 (`parse_schedule_file`) | **유지·확장** |
| `layout.py` | 바이너리 프레이밍 감지 | 유지 |
| `sch_binary.py` | raw bytes 헬퍼 | 유지 |
| **`template_writer.py`** | 템플릿 보존 필드 패치 (`patch-sch`) | **유지·확장** |
| `current_rescaler.py` | 스텝 전류 스케일 (Ensol 로직 in-tree화) | 유지 |
| `writer.py` | IR → 전체 .sch (stub 헤더) | 실험적; `build --allow-experimental-output` 전용 |
| `reader.py` | ASSB vendor thin wrapper | **삭제 예정** → `sch_parser`로 통합 |

### `schema/` — 바이너리·장비 지식

| 파일/폴더 | 역할 |
|-----------|------|
| **`ensol_v612.py`** | 612B 스텝 오프셋 (writer/reader **정본**) |
| `fields.py` | 역공학 증거 레지스트리 (confidence 태그). I/O에는 `ensol_v612` 우선 |
| `enums.py` | step type 상수 |
| `v0x00010003_612.py` | 버전별 레코드 크기 |
| `layouts.py` | file version → 기본 layout; per-unit은 registry 참조 |
| `equipment.py` | `EQUIPMENT_CURRENT_RATINGS.json` 로더 |
| `equipment_registry.py` | `EQUIPMENT_REGISTRY.json` (CTS build, layout, zip 정책) |
| `lab_corpus.py` | `PNE##.zip` only 정책 enforcement |
| `reference/` | 공식 xlsx·JSON 스펙 (읽기 전용 참조) |

### `edit/` / `resume/` / `ui/`

- **`edit/bulk_edit.py`** — `.schproj` 모듈 파라미터 일괄 변경 (CLI `bulk-edit`).
- **`resume/checkpoint.py`, `resume/splice.py`** — CSV/StepEnd에서 재개 지점 계산, 템플릿 splice.
- **`ui/`** — tkinter. 비즈니스 로직은 `ir/`, `resume/`, `io/`에 두고 UI는 호출만.

### `validate/`

- **`intake.py`** — Gate B controlled-pair JSON 검증.
- **`assb_parser_diff.py`** — in-tree vs ASSB vendor 파서 diff.
- `roundtrip.py` — write→read 검증 (현재 미사용 export; 정리 대상).

### `tools/` — 오프라인 분석 CLI

| 스크립트 | 역할 |
|----------|------|
| **`analyze_pne_unit_corpus.py`** | `PNE##.zip` 코퍼스 통계 (정본) |
| **`compare_pne_units.py`** | 유닛 간 layout·분류 diff |
| **`analyze_unknown_corpus.py`** | unknown 파일명 패턴 스캔 |
| `compare_sch.py` | 두 .sch 바이너리 diff (`compare` CLI) |
| `compare_step_layouts.py` | 612 vs 696 레이아웃 비교 |
| `assb_parser_diff_report.py` | ASSB diff 리포트 생성 |
| `build_fixture_catalog.py` | `example/fixtures/catalog.json` 유지 |
| `rescale_sch_current.py` | CLI 전류 리스케일 |
| `export_sch_schema_xlsx.py` | 스키마 xlsx export |

`_` 접두·`analyze_pne_zip_corpus.py` 등은 **삭제 예정** (0 import).

### `planning/` — 정책·증거·리포트 (코드 아님)

| 파일 | 내용 |
|------|------|
| `LAB_DATA_POLICY.md` | PNE##.zip only, per-unit layout, CTS build |
| `EQUIPMENT_REGISTRY.json` | 유닛별 관측 layout·CTS·zip 허용 |
| `EQUIPMENT_CURRENT_RATINGS.json` | 공식 권장 최대 전류 tier |
| `GOLDEN_FIXTURES_LOCKED.json` | 회귀 테스트 고정 fixture |
| `PNE_UNIT_CORPUS.json` / `.md` | 코퍼스 분석 출력 |
| `ROADMAP.md` | 구조 분석·구현 로드맵 |

코퍼스 리포트 JSON은 **도구 출력물**이다. 수동 편집하지 않고 도구를 재실행한다.

### `vendor/`

- **`assb_sch/`** — ASSB SCH 파서 (diff·parity 검증용).
- **`ensol_sch_maker_ref/`** — Ensol zip 참조. **`battery_scheduler/`** 만 active 참조.
- **`project_archive/`** — 삭제 예정 (0 import, git 외부 보관 불필요).

vendor 코드는 **가져오기(copy-in) 후 in-tree에서 수정**한다. vendor를 runtime에서 직접 import 하지 않는다 (ASSB parser 예외는 `io/reader` 경유로 축소 중).

### `example/`

- **`fixtures/`** — golden `.sch`, zip, `catalog.json`.
- **`reports/`** — tools 출력 샘플 (stale JSON은 삭제 가능).
- **`*.schproj`** — 모듈 연결·편집 데모.

### `tests/`

- `golden_fixtures.py` + `test_golden_*.py` — locked fixture 회귀.
- `test_*` — 패키지별 단위·통합.
- 새 기능은 **같은 도메인** `test_<module>.py`에 추가.

---

## 새 작업 시 체크리스트

1. `rg`로 유사 기능 검색
2. 기존 패키지에 넣을 수 있는지 확인 (`io/`, `schema/`, `tools/` …)
3. 대체 시 구버전 삭제 (주석·wrapper 없음)
4. `planning/` JSON·MD가 필요하면 **하나의 정본**만 유지 (registry vs ratings 역할 분리 유지)
5. `pytest` 실행
6. equipment 실행 가능 출력이면 Gate B intake·golden 업데이트 여부 검토

---

## 관련 문서

| 문서 | 내용 |
|------|------|
| [`planning/README.md`](README.md) | planning 폴더 인덱스 |
| [`README.md`](../README.md) | 설치·Quick start |
| [`docs/README.md`](../docs/README.md) | 사용 가이드·프로토콜·재개 |
| [`docs/GATE_B.md`](../docs/GATE_B.md) | Gate B 검증·ASSB·Q_nom |
| [`planning/ROADMAP.md`](ROADMAP.md) | 구현 로드맵·변경 이력 |
| [`planning/LAB_DATA_POLICY.md`](LAB_DATA_POLICY.md) | 코퍼스·장비 데이터 정책 |
| [`planning/LAB_CORPUS_REPORT.md`](LAB_CORPUS_REPORT.md) | 충방전기별 zip 코퍼스 리포트 (생성물) |

---

## 코드 정리 워크플로 (재사용)

「코드 정리해줘」 요청 시 아래 순서로 실행한다.

### 1단계 — 미사용 목록 (삭제 금지)

grep으로 import/호출 0건 항목을 표로 분류:

| 분류 | 기준 |
|------|------|
| **어디서도 안 쓰임** | 참조 0, 진입점 아님 |
| **한 곳에서만 쓰임** | 참조 1건 |
| **확실치 않음** | CLI 진입점, 동적 로딩, 리플렉션 |

### 2단계 — 중복 구현 (삭제 금지)

동일 로직·이중 API 그룹별 유지/삭제 제안 + 영향 호출부.

### 3단계 — 미사용 의존성 (삭제 금지)

`pyproject.toml` / `requirements.txt` 대비 실제 import.

### 4단계 — 삭제 실행

**「어디서도 안 쓰임」만** 삭제. orphan import·미사용 의존성 정리. `pytest` 통과 확인, 실패 시 롤백.

---

*Last updated: 2026-09-02*
