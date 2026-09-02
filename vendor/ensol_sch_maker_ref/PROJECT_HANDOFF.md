# Battery Scheduler (.sch Generator) — 프로젝트 인계 문서

작성일: 2026-04-14
대상: Codex CLI에서 본 프로젝트를 이어서 작업할 AI/개발자

---

## 1. 프로젝트 개요

PNE CTSeditorPro용 `.sch` 바이너리 파일을 GUI에서 자연어/블록 기반으로 작성하게 해 주는 Flask 웹앱.

- 사용자: 한국인 배터리 연구자/엔지니어 (본 문서 전체 한글, 공식 톤)
- 날짜 형식: `YYYY-MM-DD`
- 파일 삭제 전 반드시 사용자 확인
- 스택: Flask + HTML + Vanilla JS + Bootstrap 5 + Sortable.js + Mermaid.js

### 실행

```bash
cd "C:\Users\QNam\Documents\Claude\Projects\SCH 파일 자연어 작성\battery_scheduler"
python app.py
# 또는
flask --app app run --debug
```

브라우저에서 코드 변경 시 **하드 리프레시(Ctrl+F5)** 필수.

---

## 2. 디렉토리 구조

```
SCH 파일 자연어 작성/
├─ PROJECT_HANDOFF.md                 ← 본 문서
├─ battery_scheduler/
│   ├─ app.py                         # Flask 엔트리, API 엔드포인트
│   ├─ sch_core.py                    # .sch 바이너리 생성 핵심 (약 470줄)
│   ├─ mermaid_gen.py                 # 스텝 다이어그램 Mermaid 생성
│   ├─ saved/                         # 사용자가 저장한 스케줄 JSON
│   ├─ static/
│   │   ├─ css/style.css
│   │   └─ js/app.js                  # 프론트엔드 로직 (약 660줄)
│   └─ templates/
│       └─ index.html
```

---

## 3. `.sch` 바이너리 포맷 (v2)

| 영역 | 크기 | 비고 |
|---|---|---|
| Header | 1632 bytes | 스케줄명, 안전한계, 작성자, 셀용량 등 |
| Step block | 612 bytes / step | 반복 |

### 스텝 타입 코드 (offset 8, uint16 LE)

| Code | 의미 |
|---|---|
| `3` | REST |
| `0x0101` | CCCV (CC + CV 충전) |
| `0x0201` | CCCh (CC 충전) |
| `0x0202` | CCDi (CC 방전) |
| `6` | END |
| `7` | CYCMRK (사이클 마커) |
| `8` | LOOP |

### 주요 offset (step block 내부)

| Offset | 필드 | 설명 |
|---|---|---|
| 0 | int32 | step_num (1-base) |
| 8 | uint16 | step_type |
| 52 | int32 | LOOP count (LOOP 전용) |
| 332 | float32 | ΔV threshold (mV) — 기록 조건 |
| 340 | int32 | 기록 주기 (s) |
| 384 | float32 | DOD % (capacity cutoff용) |
| 496 | uint8 | capacity cutoff mode (0x01=DOD, 0x00=100%-return) |
| 497 | uint8 | capacity ref step_num |
| 564 | int32 | LOOP goto (항상 1) |

### LOOP 동작 (중요)

- LOOP는 **앞에 있는 가장 가까운 CYCMRK**로 점프.
- `LOOP(1)` = 1회 실행, 반복 없음.
- `reset_cap=True` 플래그는 누적 용량 리셋 (capacity_check 끝에 사용).
- 결국 **"블록 = CYCMRK … steps … LOOP(n)"** 구조가 되어야 블록 경계가 명확해짐.

### CYCMRK 누락 시 버그

capacity_check 같은 블록에 CYCMRK가 빠져 있으면 해당 블록의 LOOP가 **직전 블록의 CYCMRK**로 점프 → 뷰어에서 "REST 블록에 CYCMRK 두 개" 같은 현상 발생.

---

## 4. 프론트엔드 (`static/js/app.js`)

### 주요 자료구조

- `BLOCK_META[type]`: 각 블록 타입의 기본 파라미터와 필드 정의
- 캔버스 상의 블록: `{id: 'b<uid>', type, params}`
- `buildScheduleJSON()`이 최종 서버 전송용 JSON 구성

### 특수 필드 타입

- `number`, `text`, `checkbox`, `select` 외에 **`block_ref`**: 캔버스 내 특정 타입 블록 id를 동적으로 옵션 채움.
  - 현재 편집 중인 블록보다 앞에 위치한 것만 후보로 제공.
  - 사용처: `soc_setting.capacity_ref_block_id`, `pulse_test.capacity_ref_block_id` (=참조할 capacity_check 블록).
- `showIf`: 다른 필드 값에 따라 조건부 렌더. select/checkbox change 시 재렌더 (`captureInputsToParams` 로 현재 입력 보존).

### 블록 팔레트 구성

| 섹션 | 블록 |
|---|---|
| 준비 | capacity_check, soc_setting, rest |
| 단순 충방전 | charge, discharge |
| 시험 | cycle, rate_test, pulse_test |

### charge / discharge 필드

**charge**: `count`, `charge_mode`(cccv|cc), `charge_c_rate`, `charge_voltage_V`, `cv_cutoff_c`(showIf cccv), `time_limit_h`, `rest_min`, `record_time_s`, `voltage_change_mV`

**discharge**: `count`, `discharge_c_rate`, `discharge_voltage_V`, `rest_min`, `record_time_s`, `voltage_change_mV`

---

## 5. 백엔드 핵심 (`sch_core.py`)

### 헬퍼

- `pf(buf, off, val)` / `pi(buf, off, val)`: float32 / int32 little-endian pack-into
- `crate_to_mA(c_rate, cap_mAh)`: C-rate → mA
- `_set_cap_flag(buf, mode, ref_step, dod_pct)`: capacity cutoff 필드 세팅
- `_resolve_capa_ref(params, ctx)`: `capacity_ref_block_id` 명시 있으면 그 블록의 참조 step, 없으면 ctx의 가장 최신 capacity_check 참조

### 스텝 빌더 (각각 612 bytes bytearray 반환)

- `blk_rest(idx, dur_s, rec_s, dv_mV)`
- `blk_cccv(idx, v, mA, tl_s, cv_mA, rec_s, dv_mV)`
- `blk_ccc(idx, mA, v_cut, tl_s, rec_s, dv_mV)`
- `blk_ccc_return(idx, mA, v_cut, tl_s, rec_s, dv_mV, ref_step)` — 100%-return 복귀 충전
- `blk_ccdi(idx, mA, v_cut, tl_s=0, rec_s, dv_mV)`
- `blk_ccdi_dod(idx, mA, tl_s, rec_s, dv_mV, ref_step, dod_pct)` — DOD 기준 방전
- `blk_marker(idx)` → CYCMRK
- `blk_loop(idx, count, reset_cap=False)` → LOOP
- `blk_end(idx)` → END

### Expanders

각 블록 타입을 실제 스텝 시퀀스로 확장:

| 블록 | 현재 구조 | CYCMRK 상태 |
|---|---|---|
| `rest` | CYCMRK + REST + LOOP(1) | ✅ |
| `charge` | CYCMRK + (CCCV\|CCCh) + REST + LOOP(n) | ✅ |
| `discharge` | CYCMRK + CCDi + REST + LOOP(n) | ✅ |
| `cycle` | CYCMRK + charge+rest + discharge+rest + LOOP(n) | ✅ |
| `rate_test` | 여러 C-rate 반복, 각 사이클 CYCMRK로 래핑 | ✅ |
| `capacity_check` | CCCV + REST + CCDi + REST + LOOP(1, reset) | ❌ **CYCMRK 누락** |
| `soc_setting` | CC charge(복귀) + REST (단일 LOOP 없음) | ❌ **CYCMRK+LOOP(1) 누락** |
| `pulse_test` 초기부 | CCCV + REST (그 후 pulse 반복) | ❌ **초기 구간 CYCMRK 누락** |

### `schedule_to_binary_blocks(schedule)`

- `ctx = {"capa_ref_step": None, "capa_ref_map": {block_id: step_num}}`
- 각 블록 expander를 호출하면서 `start_idx` 관리.
- `capacity_check` 종료 시 ctx 업데이트:
  - `ctx["capa_ref_step"] = last_rest_before_loop_step`
  - `ctx["capa_ref_map"][block["id"]] = last_rest_before_loop_step`
- 최종 END 스텝 append.

### `schedule_to_sch(schedule) -> bytes`

`make_header(...) + b"".join(step_bytes)` 반환.

---

## 6. API 엔드포인트 (`app.py`)

| Method | Path | 동작 |
|---|---|---|
| GET | `/` | index.html |
| POST | `/api/preview` | JSON 받아 mermaid 다이어그램 문자열 반환 |
| POST | `/api/export` | JSON → `.sch` 바이너리 다운로드 |
| POST | `/api/save` | saved/에 스케줄 JSON 저장 |
| GET | `/api/list_saved` | 저장된 파일 목록 |
| GET | `/api/load?name=...` | 저장된 JSON 로드 |

패턴:
```python
data = request.get_json(force=True)
raw  = schedule_to_sch(data)
buf  = io.BytesIO(raw)
return send_file(buf, as_attachment=True,
                 download_name=f'{name}.sch',
                 mimetype='application/octet-stream')
```

파일명/작성자: **CP949 인코딩** (PNE 툴 호환).

---

## 7. 남은 작업 (우선순위)

### 7.1 CYCMRK 래핑 보정 (최우선)

**목표**: 모든 최상위 블록이 CYCMRK로 시작해 LOOP로 닫히게 통일 → double CYCMRK 버그 제거.

1. `expand_capacity_check` 시작부에 `blk_marker(idx)` 추가.
   ```python
   blocks.append(blk_marker(idx)); idx += 1
   # 기존 CCCV + REST + CCDi + REST + LOOP(1, reset) 유지
   ```
   LOOP가 이 새 CYCMRK로 점프하게 되어 이전 REST의 CYCMRK와 충돌 해소.

2. `expand_soc_setting` 전체를 CYCMRK + ... + LOOP(1)로 감싸기.

3. `expand_pulse_test` 초기 CCCV+REST 구간을 별도 CYCMRK + ... + LOOP(1)로 감싸기 (펄스 반복부는 이미 래핑돼 있음).

### 7.2 검증

다음 verify 스크립트 패턴으로 구조 확인 (`outputs/verify_*.py` 참고):

```python
import struct, sys
sys.path.insert(0, '.')
from sch_core import schedule_to_sch

schedule = {...}  # 테스트 조합
raw  = schedule_to_sch(schedule)
body = raw[1632:]
N    = len(body)//612
NAMES = {3:'REST',0x0101:'CCCV',0x0201:'CCCh',0x0202:'CCDi',
         8:'LOOP',6:'END',7:'CYCMRK'}
for i in range(N):
    o     = i*612
    snum  = struct.unpack_from('<i',body,o)[0]
    stype = struct.unpack_from('<H',body,o+8)[0]
    cnt   = struct.unpack_from('<i',body,o+52)[0]
    extra = f'  count={cnt}' if stype==8 else ''
    print(f'  step {snum:2d}  {NAMES.get(stype,hex(stype)):<10}{extra}')
```

REST → capacity_check 조합에서 기대 결과:
```
step 1 CYCMRK / 2 REST / 3 LOOP(1)          ← REST 블록
step 4 CYCMRK / 5 CCCV / 6 REST / 7 CCDi / 8 REST / 9 LOOP(1)   ← capacity_check
step 10 END
```

### 7.3 보류 과제

- `.sch` 파일 **import** 기능 (바이너리 → 블록 JSON 역변환).
- rate_test / pulse_test UI 필드 추가 검토.
- mermaid diagram에서 CYCMRK-LOOP 경계 시각화 개선.

---

## 8. 개발 중 겪은 이슈와 해결

| 증상 | 원인 | 해결 |
|---|---|---|
| `sch_core.py` 내용이 `"header = ma"` 등에서 절단 | Edit tool(Win 경로) vs Linux mount 간 파일 상태 불일치 | bash 히어독 `cat > file << 'PYEOF' ... PYEOF`로 전체 재작성 |
| bash 히어독 내 `\!=` SyntaxError | bash history expansion 이스케이프 | verify 스크립트를 별도 `.py` 파일로 작성 후 `python3`로 실행 |
| 변경 사항이 실행에 반영 안 됨 | `__pycache__` 잔존 | `find battery_scheduler -name __pycache__ -exec rm -rf {} +` |
| 브라우저 UI 변화 없음 | 정적 파일 캐시 | **Ctrl+F5 하드 리프레시** |

### 파일 상태 점검용 one-liner

```bash
python3 -c "
with open('battery_scheduler/sch_core.py','r',encoding='utf-8') as f:
    s=f.read()
print(len(s),'chars'); print(repr(s[-80:]))
"
```

---

## 9. 사용자 선호 (Codex CLI에서 유지할 것)

- 모든 대화/주석/문서 **한글**, 공식 톤.
- 날짜는 **YYYY-MM-DD**.
- 파일/데이터 삭제 전 반드시 사용자에게 확인.
- 실행 요청(“만들어줘”)은 바로 실행, 사고 요청(“어떻게 할까”)은 소크라테스식으로 질문 먼저.

---

## 10. 자주 쓰는 테스트 스케줄 템플릿

```python
base_safety = {
    'max_voltage_V':4.3,'min_voltage_V':2.0,
    'max_current_mA':500,'min_current_mA':-500,
    'max_capacity_mAh':200,'max_temp_C':70,
}

# REST + charge + discharge
schedule = {
    'schedule_name':'Test','cell_capacity_mAh':100.0,'author':'test',
    'safety': base_safety,
    'blocks':[
        {'id':'b1','type':'rest',
         'params':{'duration_min':30,'record_time_s':30,'voltage_change_mV':10}},
        {'id':'b2','type':'charge',
         'params':{'count':2,'charge_mode':'cccv','charge_c_rate':0.5,
                   'charge_voltage_V':4.2,'cv_cutoff_c':0.05,'time_limit_h':48,
                   'rest_min':30,'record_time_s':30,'voltage_change_mV':10}},
        {'id':'b3','type':'discharge',
         'params':{'count':3,'discharge_c_rate':0.5,'discharge_voltage_V':2.5,
                   'rest_min':30,'record_time_s':30,'voltage_change_mV':10}},
    ]
}
```

---

## 11. 첫 한 수 (Codex CLI가 재개하자마자 할 일)

1. `battery_scheduler/sch_core.py`의 `expand_capacity_check` 함수 첫 줄에 `blk_marker` 추가.
2. `expand_soc_setting` / `expand_pulse_test` 초기 구간에 CYCMRK+LOOP(1) 래핑.
3. 위 §7.2 검증 스크립트로 REST→capacity_check 조합의 스텝 구조 확인.
4. `.sch` 파일을 실제 PNE CTSeditorPro에서 열어 “REST 블록에 CYCMRK 두 개” 증상 해소 여부 확인.
5. 문제 없으면 cycle / rate_test / pulse_test 통합 시나리오로 회귀 테스트.

끝.
