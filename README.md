# pne_scheduler

PNE 사이클러용 `.sch` 스케줄을 **읽기·해석·생성·재개**하는 Python 패키지입니다.  
ASSB 실험실 프로토콜(FM, capacheck, cycle, RPT, QPEED 등)과 셀 형상(FP, L-level, xMyU) 추론을 지원합니다.

[![Tests](https://img.shields.io/badge/tests-78%20passed-brightgreen)](#테스트)

## 설치

```powershell
git clone https://github.com/Hwiho/pne_scheduler.git
cd pne_scheduler
pip install -e ".[dev]"
```

## 빠른 시작

```powershell
# 스케줄 뷰어 (GUI)
python run_pne_scheduler_viewer.py

# 프로젝트 에디터 — 모듈 일괄 수정 (GUI)
python run_pne_scheduler_editor.py

# 중단 실험 재개 (GUI)
python run_pne_scheduler_resume.py

# CLI
python run_pne_scheduler.py info example/example.schproj
python run_pne_scheduler.py build example/example.schproj -o output.sch
python run_pne_scheduler.py view path\to\file.sch
```

## CLI 요약

| 명령 | 설명 |
|------|------|
| `view [file.sch]` | 스텝 테이블 + FP/L/C-rate/프로토콜 표시 |
| `edit [file.schproj]` | 프로젝트 에디터 GUI |
| `info file.schproj` | 프로젝트 요약 |
| `build file.schproj -o out.sch` | `.schproj` → `.sch` 컴파일 |
| `bulk-edit ...` | 모듈 파라미터 일괄 수정 |
| `resume sch data.csv -o resumed.sch` | 중단 실험 재개 스케줄 생성 |

## Schedule viewer

```powershell
python run_pne_scheduler_viewer.py
# 또는
python -m pne_scheduler view path\to\file.sch
```

스텝 테이블과 함께 **L-level**, **footprint(FP)**, **mono/multi**, **C-rate**, **프로토콜**을 추론해 표시합니다.

### 추론 파이프라인

```
filename → FP (1818, 3350, …) → mono/multi (기본 mono) → L-level → Q_nom → C-rate
```

| 항목 | 규칙 |
|------|------|
| **FP** | `1818`, `3350`, `70150`, `70295`, `101295` (mm 로딩) |
| **Si 조합** | `6040`, `6535`, `7030` — FP가 아님 |
| **L-level** | `L5.0`, `L.4.36` 등; 모노 미표기 → **L5.0** |
| **multi** | `8M1U`, `8M2U` → **K = M × U** (양면전극 수) |
| **C-rate** | `I / Q_nom`, `Q_nom = 21600 mAh × (area/16.5) × (L/4.3) × K` |

## Bulk edit (modules)

```powershell
# GUI
python run_pne_scheduler_editor.py

# CLI — cycle_life 모듈 전체 0.5C
python -m pne_scheduler bulk-edit example/example.schproj --type cycle_life --set charge_c_rate=0.5

# CLI — 선택 id
python -m pne_scheduler bulk-edit proj.schproj --ids cyc1,cyc2 --set loop_count=300

# CLI — 모든 모듈 (호환 키만)
python -m pne_scheduler bulk-edit proj.schproj --all --set rest_s=600
```

값: `C/3`, float, int, JSON list (`[0.8,0.5,0.2]`) 지원.

## Resume interrupted experiment

원본 `.sch` + StepEnd/raw CSV로 중단 지점을 찾아 이어서 실험할 스케줄을 생성합니다.

```powershell
python run_pne_scheduler_resume.py

python -m pne_scheduler resume original.sch channel_StepEnd.csv -o resumed.sch --plan-only
python -m pne_scheduler resume original.sch channel_StepEnd.csv -o resumed.sch
python -m pne_scheduler resume original.sch channel_StepEnd.csv -o resumed.sch --step 12 --loops 150
```

- StepEnd 마지막 행 → 마지막 완료 CTS step (`SCH step = CTS - 1`)
- `* Complete` → 다음 SCH step부터 재개
- 중간 끊김 → 같은 SCH step부터 재개
- LOOP 스케줄 → 남은 loop 자동 추정 (`--loops`로 override)

자세한 내용: [docs/RESUME.md](docs/RESUME.md)

## Lab protocol defaults

| 실험 | 기본 C-rate | 비고 |
|------|-------------|------|
| **FM (formation)** | 0.1C | charge/discharge |
| **Capacheck / derating** | 0.1C → C/3 | 가끔 C/3×2 |
| **Cycle** | 0.5C | 생성·해석 기본값 |
| **In-situ cycle** | 0.5C | RPT 블록 없음 |
| **RPT** | C/3 방전 | DC-IR @ SOC 80/50/20, 1.0–1.5C |

자세한 내용: [docs/PROTOCOL.md](docs/PROTOCOL.md)

## 패키지 구조

```
pne_scheduler/
├── schema/          # .sch 바이너리 필드·enum
├── ir/              # Schedule IR (.schproj)
├── engine/          # C-rate engine, compiler
├── modules/         # formation, cycle_life, RPT, DC-IR, QPEED …
├── protocol/        # 실험 프로토콜 기본값·추론
├── stack/           # FP, L-level, xMyU, 용량 추론
├── classify/        # 파일명 → 실험 카테고리
├── edit/            # 모듈 일괄 수정
├── resume/          # 중단 재개·스플라이스
├── io/              # reader / writer
├── ui/              # viewer, editor, resume wizard
├── tools/           # 배치 분석 CLI
├── example/         # fixture + 분석 리포트
├── docs/            # 사용 가이드
└── tests/
```

## 예제 데이터

- `example/fixtures/capacheck_zip/` — capacheck/QPEED/RPT fixture 8개
- `example/fixtures/sch_lab_zip/` — 실험실 `.sch` 93개
- `example/analysis/` — 배치 분석 JSON 리포트

## 테스트

```powershell
python -m pytest tests/ -q
```

## 문서

- [사용 가이드](docs/GUIDE.md)
- [프로토콜 & C-rate](docs/PROTOCOL.md)
- [중단 실험 재개](docs/RESUME.md)
- [로드맵](planning/ROADMAP.md)

## 관련 저장소

이 패키지는 [pne-studio](https://github.com/Hwiho/pne-studio) 모노레포에서 분리된 독립 프로젝트입니다.
