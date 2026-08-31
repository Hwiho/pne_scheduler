# pne_scheduler 사용 가이드

PNE 사이클러 `.sch` 스케줄을 **읽기·해석·생성·재개**하는 도구 모음입니다.

## 설치

```powershell
git clone https://github.com/Hwiho/pne_scheduler.git
cd pne_scheduler
pip install -e ".[dev]"
```

## CLI

| 명령 | 설명 |
|------|------|
| `python -m pne_scheduler view [file.sch]` | 스케줄 뷰어 GUI |
| `python -m pne_scheduler edit [file.schproj]` | 프로젝트 에디터 (일괄 수정) |
| `python -m pne_scheduler info file.schproj` | 프로젝트 요약 |
| `python -m pne_scheduler build file.schproj -o out.sch` | `.schproj` → `.sch` 컴파일 |
| `python -m pne_scheduler bulk-edit ...` | 모듈 파라미터 일괄 수정 |
| `python -m pne_scheduler resume sch data.csv -o resumed.sch` | 중단 실험 재개 스케줄 |

## 런처 스크립트

```powershell
python run_pne_scheduler_viewer.py
python run_pne_scheduler_editor.py
python run_pne_scheduler_resume.py
```

## 셀 해석 파이프라인

```
파일명 → FP(로딩) → mono/multi → L-level → Q_nom → C-rate
```

| 항목 | 규칙 |
|------|------|
| **FP** | `1818`, `3350`, `70150`, `70295`, `101295` (mm 기준 로딩) |
| **Si 조합** | `6040`, `6535`, `7030` — FP 아님 |
| **L-level** | `L5.0`, `L.4.36` 등 파일명 명시; 모노 미표기 → **L5.0** |
| **스택** | `8M1U`, `8M2U` → **K = M × U** (양면전극 수) |

## 실험 프로토콜 기본 C-rate

| 실험 | C-rate |
|------|--------|
| FM (formation) | 0.1C |
| Capacheck / derating | 0.1C → C/3 (가끔 C/3×2) |
| Cycle / in-situ | 0.5C |
| RPT | 방전 C/3 + DC-IR @ SOC 80/50/20 (1.0~1.5C) |
| QPEED / QC | >2.5C |

자세한 내용: [PROTOCOL.md](PROTOCOL.md), [RESUME.md](RESUME.md)

## 예제 데이터

- `example/fixtures/capacheck_zip/` — 8개 capacheck/QPEED/RPT fixture
- `example/fixtures/sch_lab_zip/` — 93개 실험실 `.sch` (분석 리포트: `example/analysis/`)

## 테스트

```powershell
python -m pytest tests/ -q
```
