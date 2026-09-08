# Gate E 실행 계획 — 모듈형 스케줄 UX

개정: 2026-09-08
근거: 현재 `ui/`, `ir/`, `modules/`, `io/template_writer.py`, Gate D 검증 코드 실측,
[`UI_UX_NOTES.md`](UI_UX_NOTES.md),
[`PATTERN_VALIDATION_PLAN.md`](PATTERN_VALIDATION_PLAN.md).

---

## 1. 결론

Gate E는 바로 진행해도 된다. 다만 기존 계획처럼 **내보내기 모델부터 크게 만든 뒤
UI를 붙이는 순서**는 수정한다. 먼저 다음 두 계약을 고정해야 한다.

1. 여러 모듈을 한 절차로 합칠 때의 `END`/LOOP/step 번호 규칙
2. 모듈·패턴이 `prototype`인지, CTSPro reopen까지 검증됐는지 보여 주는 신뢰도 규칙

권장 제품 형태는 **하나의 데스크톱 셸 + 선형 Procedure가 기본 화면**이다.
LabVIEW식 그래프는 모듈 간 순서를 보는 보조 뷰로 유지한다. 현재 스케줄은 선형 실행이
핵심이므로 자유 그래프를 기본 저작 화면으로 삼으면 연결 UX가 실제 실행 모델보다 앞서간다.

패턴 검증과 Gate E는 병행할 수 있지만 경계는 명확하다.

- Setup, Procedure, Inspector, 저장/복구 UX: 패턴 검증 전에도 진행
- 기본 Module palette에 패턴을 `verified`로 노출: 해당 패턴 승인 후
- from-scratch export를 안전한 경로로 노출: 일괄 패턴 reopen 검증 후
- `equipment-ready` 표시: Gate F의 정확한 파일 hash + 대상 장비 승인 후

---

## 2. 현재 상태와 확인된 격차

| 영역 | 현재 구현 | 추가로 필요한 것 |
|------|-----------|------------------|
| 앱 구조 | viewer, flow, bulk editor, resume가 별도 창/진입점 | 단일 셸, 공통 문서 상태와 메뉴 |
| Procedure | 모듈 그래프와 확장 preview | primitive/module 혼합 순서, 삽입·이동·삭제 |
| 파라미터 | raw JSON 편집 | 단위·범위·설명·근거가 있는 필드 메타데이터와 폼 |
| Module palette | 등록된 모든 모듈을 동일 취급 | 사용자 노출 여부, 패턴 variant, 검증 등급 |
| 검증 | 그래프 연결 + 일부 module `validate()` | step/mode 필수값, V/I/시간, LOOP, END, 증거수준 통합 검증 |
| Import | `.sch` viewer만 존재 | 원본 hash/바이트를 보존하는 import session |
| Export | flow editor에는 없음; CLI build/patch는 분리 | preflight 결과와 patch/build 경로를 UI에서 안전하게 연결 |
| 데스크톱 기본기 | load/save는 있으나 앱별 구현 | dirty 표시, undo/redo, autosave/recovery, 최근 파일, 종료 확인 |
| UI 테스트 | flow model/theme 위주 | controller/widget smoke, 사용자 시나리오 회귀, 큰 파일 반응성 |

2026-09-09 구현 후 기준 상태: 로컬 전체 테스트 `424 passed, 1 skipped`;
Gate D report `49 pass / 0 fail / 0 skip`.
이 수치는 소프트웨어 구조 검증 결과이며 각 패턴의 실험 절차 충실도나 장비 실행 승인을
의미하지 않는다.

기본 워크스페이스 화면은 **PySide6/QML**(`ui/workspace_qt.py` + `ui/qml/`)이다. Tk 구현
(`ui/workspace.py`)은 같은 다섯 화면의 대체 경로로 남고, PySide6가 없는 환경에서만
`ui/__init__.py:launch_workspace()`가 이쪽을 고른다. 두 구현 모두 결정은 갖지 않고
`ui/workspace_model.py`를 그대로 구동하므로, 화면 계층을 바꿔도 검증 규칙은 한 곳에 있다.

---

## 3. UI보다 먼저 고칠 P0 도메인 계약

### 3.1 모듈 합성 규칙

현재 일부 모듈(`cycle_life`, `capacheck`, `qpeed:soc_setting`)은 자체 `END`를
내보내고, LOOP 대상은 모듈 내부 기준 숫자를 그대로 가진다. 이 상태로 앞뒤에 다른
모듈을 붙이면 다음 문제가 생길 수 있다.

- 중간 `END` 뒤에 스텝이 이어짐
- 두 번째 이후 모듈의 LOOP가 자기 시작점이 아니라 전체 schedule의 엉뚱한 step으로 감
- 값 없는 LOOP(`goto`/`count` 미지정)가 구조 테스트를 통과함

MVP 계약은 다음으로 고정한다.

- 모듈은 **schedule fragment**를 반환하고 최종 `END` 소유권은 composer가 가진다.
- LOOP 대상은 raw 절대 번호가 아니라 fragment 내부 label/reference로 표현한 뒤 합성 시
  절대 step 번호로 resolve한다.
- LOOP에는 유효한 target과 count가 모두 있어야 한다.
- 최종 결과에는 정확히 한 개의 마지막 `END`만 허용한다.
- 모듈에서 확장된 step은 기본적으로 읽기 전용이다. 사용자가 개별 step을 바꾸려면
  모듈 파라미터를 수정하거나 명시적으로 **Detach to primitives** 한다.

종료 기준: 두 개 이상의 loop 모듈을 앞뒤로 합친 회귀 테스트에서 모든 target이 해당
fragment 안을 가리키고, non-final/multiple END가 오류로 차단된다.

### 3.2 패턴 카탈로그와 신뢰도

Python dataclass 자동 introspection만으로는 제품용 폼을 만들기 부족하다. 각 primitive /
module / preset에 다음 metadata가 필요하다.

- 표시명, 설명, 카테고리, variant
- 파라미터 타입, 단위, 최소/최대, 기본값, 도움말
- 지원 layout/PNE profile
- `prototype` / `software-checked` / `CTSPro-reopen-verified` /
  `equipment-run-verified` 상태
- 알려진 제한(`fEndC`, DCR, 696, header convention 등)
- `internal_only` 플래그 (`smoke_*`는 일반 palette에서 숨김)

종료 기준: UI와 검증 runner가 같은 catalog를 읽으며, 근거가 없는 패턴은 숨겨지거나
명확한 badge와 차단 사유를 표시한다.

### 3.3 통합 preflight validator

검증 로직을 Tk widget 밖의 순수 도메인 코드로 둔다. 최소 차단 항목:

- cell/equipment profile 누락, 비정상/비유한 수치
- step type/mode별 필수 파라미터 누락
- Vmin/Vmax 및 장비 최대 전류 위반
- 0 이하 C-rate/시간, CV cutoff 역전
- LOOP target/count 오류, dangling reference
- END 누락/중복/non-final END
- 지원하지 않는 layout/step type
- writer-ready가 아닌 필드를 production 경로에서 사용

경고와 오류는 문자열만 반환하지 않고 `code`, `severity`, `object_id`, `field`,
`evidence`, `remediation`을 가진 구조체로 반환한다. 그래야 Validate 목록 클릭 시 해당
카드/필드로 이동할 수 있다.

---

## 4. 권장 IA와 핵심 사용자 흐름

### 4.1 단일 셸

왼쪽 navigation: **Setup / Procedure / Library / Validate / Export**
Procedure 내부: 왼쪽 palette, 가운데 선형 procedure, 오른쪽 inspector,
아래 preview/문제 목록.

기존 graph canvas는 Procedure의 `Flow view` 탭으로 유지한다. 별도의 주 실행 앱으로
키우지 않는다.

### 4.2 문서 종류를 혼합하지 않는다

| 문서/세션 | 목적 | 허용 편집 | 내보내기 |
|-----------|------|-----------|------------|
| **Authored project** | primitive + module로 새 절차 설계 | 전체 저작 | experimental build, 승인 후 단계적 승격 |
| **Imported patch session** | 기존 CTS 파일의 안전한 값 수정 | writer-ready field만 | 원본 hash에 묶인 `patch-sch` |
| **Review session** | 기존 `.sch` 설명/비교 | 없음 | 없음 |
| **Resume session** | 중단 스케줄 재개 | checkpoint/loop 조정 | 기존 resume 경로 |

임의의 `.sch`를 완전한 module graph로 역변환할 수 있다고 가정하지 않는다. import는
원본 raw step/unknown bytes/template hash를 가진 별도 세션이며, `Clone as draft`는 손실
가능성을 경고하는 명시적 작업으로 둔다.

### 4.3 대표 작업의 acceptance scenario

1. 장비와 Cell Profile을 먼저 고른다.
2. palette에서 Cycle 또는 HPPC module을 넣고 폼으로 값을 바꾼다.
3. 확장 step, C-rate↔mA, 예상 시간, pattern 신뢰도/제약을 즉시 본다.
4. 오류 항목을 누르면 해당 필드/step으로 이동한다.
5. 저장 후 재실행해도 동일하게 복원된다.
6. Export에서 patch와 experimental build의 차이를 이해할 수 있다.
7. 산출물 hash, target profile, 경고, 검증 상태가 manifest와 일치한다.

---

## 5. 실행 순서

### Phase E0 — UX·안전 계약과 IA (XS)

- §4의 단일 셸과 네 문서 모드를 결정 기록
- 핵심 사용자 시나리오, 용어, 상태 badge, 차단/경고 기준 확정
- 와이어 중심 graph가 아니라 선형 Procedure를 기본 뷰로 확정

종료 기준: 이 문서의 IA와 acceptance scenario를 구현 기준으로 승인.

### Phase E0.5 — Composer + catalog + validator 기반 (L, P0)

- §3.1의 fragment/END/LOOP reference 계약 구현
- primitive/module metadata catalog 구현
- 구조화된 preflight issue 모델 구현
- `.schproj` schema version/migration 전략 추가

종료 기준: 다중 loop module 합성, invalid parameter, unsupported evidence가 모두
헤드리스 테스트에서 의도대로 pass/block 된다.

**2026-09-09 결과:** 위 기반은 구현 완료. `ir/composer.py`, `modules/catalog.py`,
`validate/preflight.py` 및 회귀 테스트가 들어갔다. HPPC 62-step, QPEED 167/11-step,
QC 3종도 catalog/pack에 연결했다. UI의 완전한 단위/범위 metadata form과
`.schproj` migration은 각각 E2/E2.3 범위로 남긴다.

### Phase E1 — 단일 셸과 문서 controller (M)

- 기존 viewer/flow/bulk/resume 기능을 한 셸에서 진입
- dirty 상태, Save/Save As, 종료 확인, undo/redo command stack
- autosave/recovery와 최근 파일
- 기존 앱 진입점은 당분간 호환 wrapper로 유지

종료 기준: 새 프로젝트 작성→저장→재열기, unsaved 종료 차단, undo/redo 시나리오 테스트.

### Phase E2 — Setup + Procedure + Inspector (L)

- Cell/equipment JSON을 검증 폼으로 교체
- primitive 삽입/이동/삭제, module 삽입/재정렬
- C-rate↔mA, 전압·전류 limit, 예상 시간 즉시 preview
- module step은 read-only expansion; `Detach to primitives` 제공
- raw JSON은 Advanced/debug 경로로만 유지

종료 기준: 키보드만으로도 대표 Cycle을 만들 수 있고 저장 round-trip이 유지된다.

### Phase E2.2 — 검증 등급이 있는 Module/Pattern palette (M)

- [`PATTERN_VALIDATION_PLAN.md`](PATTERN_VALIDATION_PLAN.md)의 패턴 catalog 연결
- Formation, capacheck/derating, Cycle, QC variants, RPT/DCIR, HPPC,
  QPEED full/SOC-setting을 variant별로 분리
- 미검증 패턴은 기본값으로 실행 가능하게 보이지 않도록 badge/필터/차단 적용

종료 기준: 사용자 palette와 검증 pack이 같은 recipe/version을 참조한다.

### Phase E4 — Import/patch session (L)

- `.sch` 원본 hash, layout, raw bytes, parsed steps를 보존하는 import model
- writer-ready field만 편집 가능한 property form
- project graph와 억지로 동일 모델로 변환하지 않음
- template diff → patch plan → `patch-sch` → declared-range-only 검증

종료 기준: 무변경 import/export는 byte-identical, 허용 field 변경은 선언 범위만 바뀌고,
topology/unknown field 편집은 차단된다.

### Phase E3 — Validate/Export UX (M)

- 구조화된 issue 목록, inline badge, 문제 위치 이동
- `Patch existing`와 `Experimental build`를 별도 카드/버튼으로 분리
- target equipment/profile 필수, hash와 release status 표시
- `analysis-only` / `CTSPro-reopen-candidate` / `CTSPro-reopen-verified` /
  `equipment-run-verified` 라벨을 manifest와 동일하게 사용

종료 기준: invalid loop, END, V/I, unverified field가 production 경로를 차단하며
UI 표시와 manifest 상태가 일치한다.

### Phase E2.3 — Library와 migration (M)

- versioned method/module preset 저장·불러오기
- equipment profile과 pattern recipe version을 함께 고정
- 오래된 `.schproj`/preset migration과 unknown field 보존

종료 기준: 구버전 fixture migration + 최신 저장 + 재열기 회귀 테스트.

### Phase E-H — UX hardening과 사용자 검수 (M)

- controller/widget construction smoke + 대표 상호작용 테스트
- 큰 100–200 step schedule의 스크롤/선택/preview 반응성
- 키보드 순서, focus, 단위 표기, resize/DPI, 오류 메시지
- 사용자 검수 스크립트: 새 Cycle 작성, 기존 SCH patch, 패턴 pack 열기

종료 기준: 자동 시나리오 green + 사용자의 실제 화면 검수 결과 반영.

---

## 6. 자체 재점검 피드백과 반영 내용

초안 계획을 코드와 실제 패턴 상태에 다시 대조해 다음을 수정했다.

| 자체 피드백 | 반영 |
|-------------|------|
| export domain을 가장 먼저 만들면 저작 UX보다 큰 내부 작업에 묶인다 | composer/catalog/validator를 먼저, patch/export는 UI 골격 뒤로 이동 |
| `.sch → IR`을 하나의 변환으로 보면 unknown bytes와 module 의미가 손실된다 | authored project와 imported patch session을 분리 |
| 모듈을 이어 붙일 때 END와 LOOP 주소 계약이 없다 | Phase E0.5를 P0로 신설, fragment reference와 composer 소유 END 규정 |
| Gate D green을 패턴 충실도로 오해할 수 있다 | pattern 등급과 별도 acceptance plan/pack 추가 |
| QPEED/QC 등 variant가 catalog에 명확하지 않다 | QPEED full/SOC-setting, QC 3종을 별도 recipe로 취급 |
| 자동 등록된 smoke module이 사용자 palette에 보일 수 있다 | `internal_only` metadata 요구 |
| 생성 step을 직접 편집했을 때 module과의 관계가 모호하다 | 기본 read-only + 명시적 Detach to primitives |
| 저장 안정성·undo·복구·migration이 누락됐다 | E1/E2.3/E-H에 desktop 기본기와 schema migration 추가 |
| 테스트가 pure model에 치우쳤다 | controller/widget smoke, 사용자 시나리오, 큰 schedule 반응성 추가 |

---

## 7. Gate E 완료 기준

Gate E는 화면이 예뻐졌다는 이유로 끝내지 않는다. 다음이 모두 필요하다.

- 대표 사용자가 JSON을 직접 쓰지 않고 Setup→Procedure→Validate를 완료
- 여러 module 합성의 END/LOOP/step 번호가 안전
- 모듈/preset의 variant·단위·지원 장비·검증 등급이 보임
- imported patch와 new build가 데이터 모델과 UI에서 분리됨
- unsafe export가 차단되고 manifest와 UI 상태가 동일
- save/reopen, undo/redo, recovery, migration 회귀가 존재
- [`PATTERN_VALIDATION_PLAN.md`](PATTERN_VALIDATION_PLAN.md)의 reopen 결과가
  palette 상태에 반영됨

From-scratch 패턴 전체가 장비 실행 승인되지 않아도 Gate E의 저작 UX는 완성할 수 있다.
다만 그런 패턴을 `verified` 또는 `equipment-ready`로 표시할 수는 없다.
