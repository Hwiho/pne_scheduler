# SCH Schedule Builder — 구조 분석 & 로드맵

## 변경 이력

| 일시 | 요약 |
|------|------|
| 2026-08-31 | 초안: `sch_file_structure_20250211.xlsx`·ASSB_Analyzer_dev·Ensol PNE converter 기반 구조 정리, 비주얼 모듈형 스케줄 빌더 로드맵 수립 |
| 2026-08-31 | `pne_scheduler/` 패키지 생성 — IR·C-rate·모듈 스텁·CLI·예제 `.schproj` |

---

## 1. 목표

PNE 사이클러용 `.sch` 바이너리 스케줄 파일을 **직접 편집기 없이** 만들 수 있게 한다.

- **LabVIEW 스타일** 모듈형 비주얼 인터페이스: 실험 블록을 끌어다 붙이고 연결
- 배터리 실험 유형을 **템플릿 모듈**로 제공 (수명, 포메이션, RPT, HPPC, DC-IR 등)
- 사용자는 **C-rate**를 입력하고, **기준 용량**으로부터 전류(A/mA)를 자동 계산
- 생성된 `.sch`는 PNE 장비에서 바로 실행 가능해야 함

---

## 2. `.sch` 파일 구조 (현재 파악)

### 2.1 출처

| 출처 | 역할 | 상태 |
|------|------|------|
| `c:\sch_file_structure_20250211.xlsx` | PNE 공식 필드 정의 (버전별) | **정본 스펙** |
| `ASSB_Analyzer_dev` → `assb_analyzer/io/pne_converter.py` | 읽기·검증·메타데이터 추출 | **가장 완성도 높은 reader** |
| `_vendor/Ensol_PNE_framework/pne_app/io/pne_converter.py` | CycleNum·DCIR reference용 부분 reader | 로컬 vendor 사본 |
| `assb_analyzer/io/cell_c_rate_reference.py` | C-rate ↔ 용량 ↔ 전류 (분석 측) | **writer에 재사용 가능한 로직** |
| `assb_analyzer/io/classification_bulk_apply.py` | 동일 SCH 구조 fingerprint 비교 | 호환 Source 일괄 적용 |

> **Writer:** `pne_scheduler/io/writer.py`에 minimal stub 구현됨 (Phase 0.3). Reader는 ASSB/Ensol parser wrapper.

### 2.2 파일 버전 (Excel 시트)

| 시트명 | `nFileVersion` | Step 필드 수 (대략) | 비고 |
|--------|----------------|---------------------|------|
| Type1 `0x00010001` | 65537 | ~90 | 구형, `szName[64]` |
| Type2 `0x00010001` | 65537 | ~90 | Type1과 유사 |
| `0x00010002` | 65538 | ~90 | |
| `0x00010003` | 65539 | ~105 | ASSB converter **기본 타깃** (`step_size=612`) |
| `0x00010004` | 65540 | ~118 | |
| `0x00010007` | 65543 | **132** (`stEISSet` 포함) | 최신, EIS 필드 추가 |

**1차 타깃 버전:** `0x00010003` + `step_size=612`  
→ ASSB converter가 이미 layout policy·DCIR SOC rule·current condition mapping을 이 조합에 맞춰 구현함.  
**2차:** `0x00010007` (EIS 실험 필요 시).

### 2.3 바이너리 레이아웃 (4개 섹션)

```
┌─────────────────────────────────────┐
│ PS_FILE_ID_HEADER                   │
│  nFileID, nFileVersion              │
│  szCreateDateTime[64]               │
│  szDescrition[128]                  │
│  szReserved[128]                    │
├─────────────────────────────────────┤
│ FILE_TEST_INFORMATION  (×2 블록)    │
│  lID, lType                         │
│  szName[], szDescription[]          │
│  szCreator[], szModifiedTime[]      │
├─────────────────────────────────────┤
│ FILE_CELL_CHECK_PARAM               │
│  fMaxVoltage, fMinVoltage           │
│  fMaxCurrent, fOCVLimitVal          │
│  fTrickleCurrent, fDeltaVoltage     │
│  lTrickleTime, nMaxFaultNo, bPreTest│
├─────────────────────────────────────┤
│ FILE_STEP_CONDITION  (×N steps)     │
│  chStepNo, chType, chMode           │
│  fVref, fIref (전압/전류 설정)      │
│  fEndTime, fEndV, fEndI, fEndC ...  │
│  Loop/Goto (nLoopInfo*, nGotoStepID)│
│  Limit (fVLimit*, fILimit*)         │
│  Sampling (fDeltaTime/V/I)          │
│  DCIR (fDCRStartTime, fDCREndTime)  │
│  SOC (fSocRate, fMaxCapacity)       │
│  ... (버전별 확장 필드)             │
└─────────────────────────────────────┘
```

### 2.4 Step Type / Mode 코드

**chType (Step 종류)**

| 이름 | 코드 | 용도 |
|------|------|------|
| CHARGE | 0x01 | 충전 |
| DISCHARGE | 0x02 | 방전 |
| REST | 0x03 | 휴지 |
| OCV | 0x04 | OCV 측정 |
| IMPEDANCE | 0x05 | 임피던스 |
| END | 0x06 | 종료 |
| CYCLE | 0x07 | 사이클 마커 |
| LOOP | 0x08 | 루프 |
| PATTERN | 0x09 | 패턴 파일 |
| BALANCE | 0x0A | 밸런스 |

**chMode (실행 모드)** — converter에서 사용하는 조합:

| 코드 | 의미 | converter 매핑 |
|------|------|----------------|
| 0x0101 | CCCV | `SCH_STEP_TYPE_CCCV` |
| 0x0201 | CC Charge | `SCH_STEP_TYPE_CC_CHARGE` |
| 0x0202 | CC Discharge | `SCH_STEP_TYPE_CC_DISCHARGE` |

**SCH ↔ CTS StepNo 관계 (중요):**

```
CTS StepNo = SCH StepNo + 1
```

ASSB `cell_c_rate_reference.py`와 `pne_converter.py` 모두 이 mapping을 전제로 current condition을 검증한다. Writer도 반드시 동일 규칙을 지켜야 한다.

### 2.5 Step record 크기

| step_size | 대응 버전 | ASSB 지원 |
|-----------|-----------|-----------|
| **612 bytes** | `0x00010003` | ✅ primary (`SCH_V0X00010003_STEP612`) |
| **696 bytes** | 신규 장비/버전 | layout detection only |

Writer 1차 구현은 **612-byte fixed layout**으로 고정하고, round-trip test로 offset 검증 후 696 확장.

### 2.6 핵심 Step 필드 (실험 모듈 설계에 필요)

| 필드 | 의미 | 모듈에서의 입력 |
|------|------|----------------|
| `fVref` | 목표 전압 (V) | 충전 상한 / 방전 하한 |
| `fIref` | 목표 전류 (mA, 장비 raw) | **C-rate × 기준용량**으로 계산 |
| `fEndTime` | 종료 시간 (sec) | Rest, HPPC pulse 간격 |
| `fEndV` | 종료 전압 | CC-CV 전환, 방전 종료 |
| `fEndI` | 종료 전류 (CV cutoff) | C/20, C/50 등 C-rate로 지정 |
| `fEndC` | 종료 용량 (mAh) | SOC setting, partial cycle |
| `fEndCVTime` | CV 구간 시간 | |
| `nLoopInfoGoto/Cycle` | 루프 대상·횟수 | 수명 실험, RPT 주기 |
| `nGotoStepID` | SOC reference step | DC-IR SOC setting |
| `fDCRStartTime/EndTime` | DCIR 측정 구간 | DC-IR 모듈 |
| `fDeltaTime/V/I` | 데이터 샘플링 | 기본 프로파일 |
| `fSocRate` | SOC 비율 | SOC setting step |
| `fMaxCapacity` | 기준 용량 (mAh) | C-rate 계산 기준 |

---

## 3. 아키텍처 제안

### 3.1 3-Layer 구조

```
┌──────────────────────────────────────────────────────────┐
│  UI Layer — Visual Flow Editor (LabVIEW style)           │
│  Node graph: drag-drop modules, wire connections         │
└────────────────────────┬─────────────────────────────────┘
                         │ project JSON (.schproj)
┌────────────────────────▼─────────────────────────────────┐
│  Domain Layer — Experiment Modules + Schedule IR         │
│  Formation / CycleLife / RPT / HPPC / DCIR / Rest ...  │
│  C-rate Engine, Loop expander, Safety validator          │
└────────────────────────┬─────────────────────────────────┘
                         │ compiled step list
┌────────────────────────▼─────────────────────────────────┐
│  Binary Layer — SCH Writer + Round-trip Validator        │
│  struct pack, version-aware offsets, PNE float32 rules   │
└──────────────────────────────────────────────────────────┘
```

### 3.2 중간 표현 (Schedule IR)

UI와 바이너리 사이에 **버전 독립 IR**을 둔다.

```python
@dataclass
class ScheduleProject:
    name: str
    cell_profile: CellProfile          # 기준 용량, Vmax/Vmin
    sch_version: int                   # 0x00010003
    modules: list[ExperimentModule]    # 그래프 노드
    connections: list[ModuleConnection]  # 실행 순서

@dataclass
class CellProfile:
    nominal_capacity_mAh: float
    v_max: float
    v_min: float
    # optional: formation capacity, DCIR pulse C-rate table

@dataclass
class StepIntent:
  # 사용자 친화적 의도 — C-rate 기반
    step_type: Literal["charge","discharge","rest","ocv","cycle","loop","end"]
    mode: Literal["CCCV","CC","CV"]
    c_rate: float | None              # fIref 산출
    cv_cutoff_c_rate: float | None    # fEndI 산출
    end_voltage_v: float | None
    end_time_s: float | None
    end_capacity_fraction: float | None  # SOC 50% → fEndC
    ...
```

모듈은 `StepIntent[]`를 생성하고, compiler가 `FILE_STEP_CONDITION` 바이트 레코드로 flatten한다.

### 3.3 C-rate Engine (요구사항 3 반영)

```
I_mA = C_rate × Q_nominal_mAh
```

| 입력 | 예시 | 산출 |
|------|------|------|
| 1C charge, 80 mAh cell | C=1.0 | I = 80 mA |
| C/3 discharge | C=0.333 | I = 26.7 mA |
| CV cutoff C/20 | C=0.05 | fEndI = 4 mA |

**UI 규칙:**
- 사용자-facing 단위는 **항상 C-rate** (전류 직접 입력은 고급 옵션으로만)
- Cell Profile에서 `nominal_capacity_mAh` 한 번 설정 → 모든 모듈에 전파
- ASSB `cell_c_rate_reference.py`의 허용 C-rate 테이블(`_ALLOWED_CURRENT_RATES`)을 preset으로 제공
- Writer 출력 시 PNE raw 단위(mA) + float32 packing (`_f32repr` 규칙) 적용

### 3.4 비주얼 UI (요구사항 1 반영)

**화면 구성:**

```
┌─────────────┬────────────────────────────────┬──────────────┐
│ Module      │  Canvas (node graph)           │ Properties   │
│ Palette     │                                │ Panel        │
│             │  [Formation]──▶[CycleLife]   │              │
│ · Formation │         │                      │ C-rate: 1C   │
│ · CycleLife │         └──▶[RPT every 50]     │ Vmax: 4.2 V  │
│ · RPT       │                                │ Loop: 500    │
│ · HPPC      │                                │              │
│ · DC-IR     │                                │              │
│ · Rest      │                                │              │
│ · Loop      │                                │              │
└─────────────┴────────────────────────────────┴──────────────┘
│ Timeline preview  │  Step table  │  Export .sch  │  Validate │
└───────────────────────────────────────────────────────────────┘
```

**기술 스택 후보:**

| 옵션 | 장점 | 단점 |
|------|------|------|
| **A. Tkinter + custom canvas** | pne_studio2와 동일 스택, 배포 단순 | node graph 직접 구현 부담 |
| **B. PySide6 + NodeEditor** | LabVIEW UX에 가까움 | 의존성 추가 |
| **C. Web (React Flow) + Electron** | 최고의 graph UX | 별도 앱, 배포 복잡 |

**권장:** Phase 3 비주얼 UI는 `pne_scheduler/ui/`에서 별도 앱으로 시작하고, 나중에 pne_studio2와 통합.

---

## 4. 실험 모듈 카탈로그 (요구사항 2)

### 4.1 Phase 1 — 필수 모듈

| 모듈 | 구성 Step 패턴 | 주요 파라미터 (C-rate 기반) |
|------|----------------|----------------------------|
| **Formation** | Charge CCCV → Rest → Discharge CC → Rest (×N cycle) | charge C, discharge C, Vmax/Vmin, cycle count |
| **Cycle Life** | [Charge CCCV → Rest → Discharge CC → Rest] × loop | C_charge, C_discharge, end condition (V or C), loop count |
| **RPT** | Reference discharge (C/3) → Rest → pseudo-OCV steps | C_ref, SOC checkpoints, anchor cycle interval |
| **DC-IR** | SOC setting discharge → Rest → pulse discharge (short CC) → Rest | SOC %, pulse C, pulse duration, DCR window |
| **HPPC** | SOC staircase + pulse train (charge/discharge pulses) | SOC list, pulse C, pulse/rest duration |
| **Rest / OCV** | Rest or OCV hold | duration, ΔV sampling |

### 4.2 Phase 2 — 확장 모듈

| 모듈 | 설명 |
|------|------|
| **Calendar Aging** | Storage at SOC X%, periodic RPT insert |
| **Rate Capability** | Multi C-rate discharge ladder |
| **GITT** | Intermittent current + rest OCV |
| **Pattern Drive** | PATTERN step + `.pat` 파일 연결 |
| **EIS** | `stEISSet` (0x00010007 전용) |
| **Self-discharge** | Long rest + periodic OCV |
| **Pre-test / Cell Check** | `FILE_CELL_CHECK_PARAM` 자동 생성 |

### 4.3 모듈 공통 인터페이스

```python
class ExperimentModule(Protocol):
    module_type: str
    def validate(self, cell: CellProfile) -> list[str]: ...
    def expand(self, cell: CellProfile) -> list[StepIntent]: ...
    def estimated_duration_h(self, cell: CellProfile) -> float: ...
    def to_dict(self) -> dict: ...
    @classmethod
    def from_dict(cls, data: dict) -> Self: ...
```

---

## 5. 추가 제안 기능 (요구사항 4)

### 5.1 안전·검증

| 기능 | 설명 |
|------|------|
| **Safety envelope** | Cell Profile V/I 한도 대비 step별 자동 검증 |
| **Round-trip validator** | Writer 출력 → ASSB `parse_sch_cycle_map_bytes` 재파싱 → 원본 IR 비교 |
| **PNE simulator hook** | 가능하면 PNE PC 시뮬레이터로 dry-run (수동 확인 체크리스트) |
| **StepNo continuity check** | 1..N 연속, END step 존재, LOOP goto 유효성 |

### 5.2 생산성

| 기능 | 설명 |
|------|------|
| **Template library** | ASSB preset (`06_assb_design_stack`) 연동 Cell Profile |
| **Import existing .sch** | 실측 sch 역파싱 → IR → 그래프 편집 (reader 확장) |
| **Clone & parameter sweep** | 동일 구조에 C-rate / cycle 수만 sweep → batch export |
| **Schedule fingerprint** | ASSB `FrozenScheduleStructureFingerprint` 호환 — 동일 구조 Source 검색 |
| **Human-readable export** | Step table Excel/PDF (공정서 첨부용) |
| **Estimated duration / throughput** | 총 예상 시간, 에너지, 사이클 수 요약 |

### 5.3 분석 연동 (pne_studio2 / ASSB 생태계)

| 기능 | 설명 |
|------|------|
| **ASSB classification hint** | 모듈 조합에서 예상 test type (formation/cycle/dcir) 자동 태깅 |
| **C-rate display sync** | ASSB Cell Manager `cell_c_rate_reference` schema와 동일 기준 용량 |
| **Sampling preset** | Δt/ΔV/ΔQ 기본값 (cyclediag IMPROVEMENT_ROADMAP #16 미해 UNKNOWN 항목 해소) |
| **Post-build checklist** | `.cts` naming, `.ini` current range, channel folder 구조 안내 |

### 5.4 고급

| 기능 | 설명 |
|------|------|
| **Conditional branching** | SOC/전압 조건 goto (nGotoStepID 시나리오) |
| **Multi-version export** | 동일 IR → 0x00010003 / 0x00010007 선택 출력 |
| **Chiller / thermal profile** | fTref, chiller 필드 (0x00010007) |
| **Version control** | `.schproj` git-friendly JSON + diff view |

---

## 6. 구현 로드맵

### Phase 0 — 구조 확정 & Spike (1~2주)

| # | 작업 | 산출물 | 완료 기준 |
|---|------|--------|-----------|
| 0.1 | Excel → Python struct schema 자동 생성 | `sch_schema_0x00010003.py` | 필드명·offset·타입 612B 전체 매핑 |
| 0.2 | 기존 실측 `.sch` 3~5개 round-trip | test fixtures | parse → (identity) → parse 동일 |
| 0.3 | Minimal writer: Rest → CC Charge → END | `write_minimal.sch` | PNE 장비 또는 시뮬레이터 로드 성공 |
| 0.4 | ASSB parser와 offset 대조 | 검증 리포트 | `fIref`·`fEndI`·goto 필드 일치 |

### Phase 1 — Core Writer + C-rate (2~3주)

| # | 작업 | 산출물 |
|---|------|--------|
| 1.1 | `ScheduleProject` IR + JSON serializer | `.schproj` format v1 |
| 1.2 | C-rate engine + CellProfile | 단위 테스트 |
| 1.3 | Step compiler (IR → binary steps) | Formation 1-cycle 생성 |
| 1.4 | Cell check param writer | header 전체 write |
| 1.5 | CLI: `python -m pne_scheduler build project.schproj -o out.sch` | 자동화 가능 |

### Phase 2 — 실험 모듈 (3~4주)

| # | 모듈 | 우선순위 |
|---|------|----------|
| 2.1 | Formation | P0 |
| 2.2 | Cycle Life (+ Loop/Cycle marker) | P0 |
| 2.3 | DC-IR (SOC setting + pulse) | P0 |
| 2.4 | RPT | P1 |
| 2.5 | HPPC | P1 |
| 2.6 | Rest/OCV utility | P1 |

각 모듈마다: **실측 sch 1개와 byte-level 또는 semantic diff** 통과.

### Phase 3 — Visual UI (4~6주)

| # | 작업 |
|---|------|
| 3.1 | Module palette + node canvas |
| 3.2 | Property panel (C-rate spinbox, V limit) |
| 3.3 | Step table live preview |
| 3.4 | Timeline / duration estimator |
| 3.5 | Export + validation feedback |
| 3.6 | Template load/save |

### Phase 4 — 고급 & 통합 (지속)

- `.sch` import (역변환)
- ASSB Analyzer fingerprint 연동
- 0x00010007 / EIS 지원
- pne_studio2 메뉴에서 Schedule Builder 실행

---

## 7. 패키지 배치 제안

```
pne_scheduler/                   # 본 패키지 (repo 루트)
├── planning/ROADMAP.md          # 본 문서
├── example/example.schproj
├── schema/
│   ├── v0x00010003_612.py
│   └── enums.py
├── ir/
│   ├── cell_profile.py
│   ├── project.py
│   └── step_intent.py
├── modules/
│   ├── formation.py
│   ├── cycle_life.py
│   ├── rpt.py
│   ├── hppc.py
│   ├── dcir.py
│   └── rest.py
├── engine/
│   ├── c_rate.py
│   └── compiler.py
├── io/
│   ├── reader.py
│   └── writer.py
├── validate/
│   └── roundtrip.py
├── ui/
│   └── flow_editor.py           # Phase 3
└── tests/

run_pne_scheduler.py             # 루트 launcher
```

**의존성:** `assb_analyzer.io.pne_converter.parse_sch_cycle_map_bytes`를 validation에 사용. 없으면 `_vendor/Ensol_PNE_framework` fallback.

---

## 8. 리스크 & 미해결 항목

| 항목 | 상태 | 대응 |
|------|------|------|
| 612 vs 696 byte step size 자동 선택 | 부분 파악 | 실측 sch로 version→size 매핑 테이블 작성 |
| PNE raw current 단위 (mA vs A) | ini range 의존 | Cell range profile + ASSB `unit_scale` 재사용 |
| `FILE_GRADE`, `STRUCT_EIS_SET` 내부 구조 | Excel에 이름만 | 0x00010007은 Phase 4로 연기 |
| Δt/ΔV/ΔQ 권장값 | cyclediag에서 UNKNOWN | 사내 표준 sch 샘플에서 역추출 |
| Writer 실기 검증 | 미착수 | Phase 0.3에서 PNE PC 1회 로드 테스트 필수 |
| GitHub repo 접근 | `lgn0427-dev/ASSB_Analyzer_dev` 확인됨 | `pne_converter.py`를 정본 reader로 삼음 |

---

## 9. 다음 즉시 액션 (이번 주)

1. **실측 `.sch` 샘플 수집** — formation / cycle+RPT / DC-IR 각 1개 이상 (사이클러에서 export)
2. **Phase 0.1** — Excel `0x00010003` 시트 → 612-byte struct offset table 코드 생성
3. **Phase 0.3 spike** — 3-step minimal sch writer + PNE 로드 테스트
4. **모듈 우선순위 확정** — Formation + Cycle Life + DC-IR 먼저 (ASSB 분류 체계와 정합)

---

## 10. 참고 코드 위치

| 경로 | 내용 |
|------|------|
| `c:\sch_file_structure_20250211.xlsx` | PNE 공식 필드 스펙 |
| `ASSB_Analyzer_dev/assb_analyzer/io/pne_converter.py` | SCH parser (read), current conditions, DCIR SOC rules |
| `ASSB_Analyzer_dev/assb_analyzer/io/cell_c_rate_reference.py` | C-rate ↔ capacity |
| `ASSB_Analyzer_dev/assb_analyzer/io/classification_bulk_apply.py` | SCH structure fingerprint |
| `_vendor/Ensol_PNE_framework/pne_app/io/pne_converter.py` | 로컬 부분 reader |
| `pne_studio2/assets/presets/06_assb_design_stack.json` | Cell 설계 preset (용량 추정 참고) |
