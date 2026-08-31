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
