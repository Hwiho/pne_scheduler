# 실험 프로토콜 & C-rate 규칙

## 표준 C-rate 프리셋

**일반:** 0.1C, 0.2C, C/3, C/2, 1C, 1.5C, 2C, 2.5C  
**급충 (QPEED/QC):** 3C, 3.5C, 4C, 4.5C, 5C, 5.5C, 6C

## 모듈별 기본값

### Formation (FM)
- charge/discharge **0.1C**
- 모듈: `formation`

### Capacheck / Derating
- **0.1C** 후 **C/3** 용량 측정
- 가끔 C/3 두 번 (`measurement_cycles=2`)
- 모듈: `capacheck`

### Cycle life
- charge/discharge **0.5C** (생성·해석 기본값)
- 모듈: `cycle_life`

### In-situ cycle
- 0.5C, **RPT 블록 없음**
- 모듈: `insitu_cycle`

### RPT
- 참조 방전 **C/3**
- SOC **80 / 50 / 20** 에서 DC-IR pulse **1.5C** (또는 1.0C)
- 모듈: `rpt` (+ `dcir`)

### QPEED
- >2.5C 급충 실험
- `SOC_setting` 은 QPEED 하위 variant
- 현재 코퍼스에서 SOC%는 `fEndC`에 저장되지 않음. full 파일은 **3.318 V** 충전을 SOC 대용으로 13회 반복한 뒤 고율로 4.2 V까지 충전
- 모듈 프리셋: `qpeed.full_3318` (fixture topology), `qpeed.soc_setting` (conditioning only), `qpeed.soc_fraction` (generator template)

### HPPC
- 모듈 생성 기본값: `hppc.full_range` (2.5–4.2 V + residual approach)
- `hppc.soc_90_50_10` 은 생성 템플릿이며 체크인 fixture와 다름
- 체크인 fixture `HPPC_Full range.sch`는 **2.5–4.2 V full range** + 30 mA residual. SOC 계단은 바이너리에 없음

### Module recipes

QPEED / HPPC / formation / cycle_life / sequence modules store an editable
`setup` + `repeat` × N + `after` list of charge, discharge, and rest units.
Rebuild from a named preset, then edit units in the flow editor. Output is
analysis-only step intents, not equipment-ready SCH.

```powershell
python -m pne_scheduler flow example/qpeed.schproj
```

### 스케줄 설명 (read-only)

```powershell
python -m pne_scheduler explain path\to\file.sch
```

파일명 SOC, 전압 setpoint, rest/LOOP 블록을 서술한다. writer-ready가 아니다.

## `.schproj` 예시

```json
{
  "modules": [
    { "id": "fm1", "module_type": "formation", "params": { "charge_c_rate": 0.1 } },
    { "id": "cyc1", "module_type": "cycle_life", "params": { "charge_c_rate": 0.5, "loop_count": 300 } }
  ]
}
```

## 일괄 수정

```powershell
python -m pne_scheduler bulk-edit project.schproj --type cycle_life --set charge_c_rate=0.5
python -m pne_scheduler bulk-edit project.schproj --all --set rest_s=600
```

GUI: `python run_pne_scheduler_editor.py`
