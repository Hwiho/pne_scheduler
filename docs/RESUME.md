# 중단 실험 재개 (Resume)

원본 `.sch` + 사이클러 데이터(StepEnd / raw CSV)로 **어디서 끊겼는지** 찾고, 이어서 실험할 `.sch`를 만듭니다.

## GUI

```powershell
python run_pne_scheduler_resume.py
```

1. **Open .sch** — 원본 스케줄  
2. **Open data** — `*StepEnd.csv` 또는 `*_raw.csv`  
3. **Analyze** — 재개 스텝·남은 loop 확인  
4. **Export resumed .sch**

## CLI

```powershell
# 계획만 확인
python -m pne_scheduler resume orig.sch channel_StepEnd.csv -o out.sch --plan-only

# 재개 스케줄 생성
python -m pne_scheduler resume orig.sch channel_StepEnd.csv -o resumed.sch

# 수동 지정
python -m pne_scheduler resume orig.sch data.csv -o resumed.sch --step 12 --loops 150
```

## 체크포인트 규칙

| 데이터 | 의미 |
|--------|------|
| StepEnd 마지막 행 | 마지막 완료 CTS step |
| SCH step | `CTS StepNo - 1` |
| `* Complete` | 다음 SCH step부터 재개 |
| 중간 끊김 | 같은 SCH step부터 재개 |
| LOOP 스케줄 | 완료 discharge 수로 남은 loop 추정 |

## 주의

- StepEnd와 `.sch` step 번호가 맞는지 Analyze 후 확인하세요.
- 원본 바이너리를 잘라 쓰므로 writer 스텁보다 장비 호환성이 좋습니다.
