# Battery Scheduler 코드베이스 리서치 보고서

작성일: 2026-04-27  
분석 대상: `/home/q_nam_2/ensol_project/sch_maker`

## 1. 프로젝트 개요

이 프로젝트는 PNE CTSPro/CTSeditorPro 계열 장비에서 사용하는 `.sch` 스케줄 바이너리를 웹 GUI에서 블록 기반으로 만들고, 일부 `.sch` 파일을 다시 편집 가능한 JSON 블록으로 가져오며, 기존 `.sch` 파일의 전류값을 셀 용량 변화에 맞춰 재스케일링하는 도구 모음이다.

핵심 애플리케이션은 `battery_scheduler/` 아래의 Flask 웹앱이다.

- 서버: Flask
- 클라이언트: HTML, Vanilla JS, Bootstrap 5, Bootstrap Icons, Sortable.js, Mermaid.js
- 핵심 산출물: PNE `.sch` 바이너리
- 주요 사용자 흐름: 블록 추가 -> 파라미터 편집 -> Mermaid 미리보기 -> `.sch` export 또는 JSON save/load
- 보조 흐름: `.sch` import -> best-effort JSON 블록 변환, `.sch` 전류 rescale CLI/GUI

`project_archive/`는 과거 구현, 폐기 스크립트, 레거시 출력물 보관소이다. 현재 실행 경로의 핵심은 `battery_scheduler/app.py`, `sch_core.py`, `sch_reader.py`, `mermaid_gen.py`, `static/js/app.js`, `templates/index.html`이다.

## 2. 현재 작업트리 상태

분석 시점에 아래 3개 파일은 이미 staged 수정 상태였다.

- `battery_scheduler/app.py`
- `battery_scheduler/static/js/app.js`
- `battery_scheduler/templates/index.html`

수정 내용은 `.sch` import 기능 추가와 관련되어 있다. 본 보고서 작성 외에는 기존 staged 변경을 되돌리거나 수정하지 않았다.

## 3. 디렉터리 구조와 역할

```text
battery_scheduler/
  app.py                         Flask 엔트리포인트 및 API
  sch_core.py                    스케줄 JSON -> .sch 바이너리 생성 핵심
  sch_reader.py                  .sch 바이너리 -> 스케줄 JSON best-effort importer
  mermaid_gen.py                 스케줄 JSON -> Mermaid flowchart 생성
  sch_current_rescaler.py        .sch 전류 필드 재스케일 CLI
  sch_current_rescaler_gui.py    tkinter 기반 전류 재스케일 GUI
  templates/index.html           단일 페이지 웹 UI
  static/js/app.js               프론트엔드 상태, 블록 편집, API 호출
  static/css/style.css           UI 스타일
  saved/MySchedule.json          저장된 예시/사용자 스케줄
  requirements.txt               Flask 의존성
```

`dist/windows/`에는 Windows 실행 파일이 있고, `project_archive/`에는 과거 자연어 파서, writer 버전, 레거시 `.sch`/`.json`/이미지 출력물이 있다.

## 4. 실행 흐름

### 4.1 웹앱 시작

`battery_scheduler/app.py`가 Flask 앱을 만든다. 직접 실행하면 1.2초 뒤 브라우저를 열고 `localhost:5000`에서 `debug=False`, `use_reloader=False`로 실행한다.

```text
python3 battery_scheduler/app.py
```

실제 서버 의존성은 `requirements.txt` 기준 `flask>=2.3.0`뿐이다. 프론트엔드 라이브러리는 CDN에서 로드한다.

### 4.2 UI에서 스케줄 작성

`templates/index.html`은 단일 화면을 구성한다.

- 상단 바: 스케줄명, 셀 용량, 안전 한계, 저장/불러오기/미리보기/export 버튼
- 좌측 팔레트: 블록 타입 선택
- 중앙 캔버스: 추가된 블록 목록, drag sort
- 우측 패널: 선택된 블록 파라미터 편집
- 모달: Mermaid preview, 저장 JSON 및 `.sch` import

`static/js/app.js`의 전역 상태가 프론트엔드의 단일 source of truth이다.

- `blocks`: 캔버스에 놓인 블록 배열
- `selectedId`: 현재 선택 블록 id
- `blockCounter`: 새 블록 id 생성 카운터
- `BLOCK_META`: 블록별 라벨, 아이콘, 기본값, 편집 필드, 요약 함수

사용자는 팔레트 버튼으로 `addBlock(type)`을 호출하고, 각 블록은 `{ id, type, params }` 형태로 `blocks`에 추가된다. `Sortable.create(canvas)`가 `.block-drag-handle` 기준 drag reorder를 처리하며, reorder 후 `blocks` 배열 순서를 갱신한다.

### 4.3 파라미터 편집

`renderParamEditor(block)`은 `BLOCK_META[type].fields`를 순회해 입력 UI를 만든다.

지원 필드 타입:

- `number`
- `text`
- `checkbox`
- `select`
- `block_ref`

`showIf`가 있으면 의존 필드 값에 따라 조건부로 렌더링된다. select/checkbox 변경 시 `captureInputsToParams()`로 현재 DOM 값을 보존한 뒤 에디터를 다시 렌더링한다. `applyParams()`는 DOM 입력값을 `block.params`에 반영하고 블록 카드 요약을 갱신한다.

`block_ref`는 현재 블록보다 앞에 위치한 특정 타입 블록만 후보로 보여준다. 현재 사용처는 `soc_setting.capacity_ref_block_id`, `pulse_test.capacity_ref_block_id`이며, `capacity_check` 블록 참조를 위해 쓰인다.

### 4.4 JSON 생성

`buildScheduleJSON()`은 서버로 보낼 최종 스케줄 객체를 만든다.

```json
{
  "schedule_name": "...",
  "cell_capacity_mAh": 100,
  "author": "user",
  "safety": {
    "max_voltage_V": 4.3,
    "min_voltage_V": 0.0,
    "max_current_mA": 0.0,
    "min_current_mA": 0.0,
    "max_capacity_mAh": 200.0,
    "max_temp_C": 70.0
  },
  "blocks": [
    { "id": "blk_1", "type": "capacity_check", "params": {} }
  ]
}
```

이 JSON이 `/api/preview`, `/api/export`, `/api/save`로 전달된다.

## 5. Flask API

`app.py`의 API는 단순한 JSON/binary adapter 역할을 한다.

| Method | Path | 역할 |
|---|---|---|
| GET | `/` | `index.html` 렌더링 |
| POST | `/api/preview` | JSON schedule을 Mermaid 코드로 변환 |
| POST | `/api/export` | JSON schedule을 `.sch` 바이너리로 변환해 다운로드 |
| POST | `/api/save` | JSON schedule을 `battery_scheduler/saved/<name>.json`으로 저장 |
| GET | `/api/list_saved` | 저장 JSON 파일 목록 반환 |
| POST | `/api/load` | 저장 JSON 파일 로드 |
| POST | `/api/import_sch` | 업로드된 `.sch`를 편집 가능한 schedule JSON으로 변환 |

중요한 보안/견고성 특성:

- 저장/로드 파일명은 `schedule_name` 또는 클라이언트 전달 filename을 그대로 `os.path.join(SAVE_DIR, ...)`에 붙인다. 현재 코드에는 path traversal 방어가 없다.
- `/api/export`의 파일명은 공백만 `_`로 바꾼다.
- `/api/import_sch`는 확장자가 `.sch`인지 확인하고, `cell_capacity_mAh`를 form 값에서 float로 읽는다.

## 6. `.sch` 바이너리 생성 핵심

핵심 파일은 `sch_core.py`이다.

### 6.1 파일 포맷 상수

- Header 크기: `1632` bytes
- Step block 크기: `612` bytes
- Magic: `b"\x71\x4d\x0b\x00\x02\x00\x01\x00"`
- File signature: `b"PNE CTSPro Schedule File."`

주요 step type:

| 코드 | 의미 |
|---:|---|
| `3` | REST |
| `0x0101` | CCCV |
| `0x0201` | CC charge |
| `0x0202` | CC discharge |
| `6` | END |
| `7` | CYCMRK |
| `8` | LOOP |

주요 step offset:

| Offset | 용도 |
|---:|---|
| `0` | step number, int32 |
| `8` | step type |
| `12` | charge voltage 또는 discharge voltage limit 계열 |
| `16` | current mA |
| `20` | duration/time limit seconds |
| `28` | discharge cutoff voltage |
| `32` | CV cutoff current |
| `52` | LOOP count |
| `88` | LOOP reset capacity flag |
| `332` | 기록 전압 변화 threshold mV |
| `340` | 기록 주기 seconds |
| `384` | DOD percent |
| `496` | capacity cutoff mode |
| `497` | capacity reference step number |
| `564` | LOOP goto |

### 6.2 Header 생성

`make_header(name, safety, author)`가 1632-byte header를 만든다.

- timestamp는 ASCII `%Y-%m-%d %H:%M:%S.000`
- author와 filename은 CP949 인코딩 우선, 실패 시 ASCII replacement
- filename은 `name + ".sch"`로 header에 기록
- safety limit은 `HOFF_SAFE = 0x3D8`부터 float로 기록
- voltage는 V 입력을 mV로 변환해 기록

### 6.3 Step builder

각 builder는 정확히 612-byte `bytes`를 반환한다.

- `blk_rest`: REST, duration/record 조건 기록
- `blk_cccv`: CCCV charge
- `blk_ccc`: CC charge
- `blk_ccc_return`: capacity reference 기반 100% return charge
- `blk_ccdi`: CC discharge
- `blk_ccdi_dod`: DOD/capacity reference 기반 discharge
- `blk_marker`: CYCMRK
- `blk_loop`: LOOP, count 및 reset flag
- `blk_end`: END

`crate_to_mA(c_rate, cap_mAh)`는 C-rate를 mA로 단순 변환한다. 즉 1C at 100mAh = 100mA이다.

### 6.4 Block expander

`EXPANDERS`가 프론트엔드 블록 타입을 expander 함수에 매핑한다. `schedule_to_binary_blocks(schedule)`는 schedule의 blocks를 순서대로 순회하며 step 번호 `idx`를 증가시키고, 마지막에 END를 추가한다.

현재 expander별 구조:

| Block type | 생성 step 구조 |
|---|---|
| `rest` | CYCMRK -> REST -> LOOP(1) |
| `capacity_check` | CYCMRK -> CCCV -> REST -> CCDi -> REST -> LOOP(1, reset_cap) |
| `soc_setting` | CCCV -> REST -> DOD CCDi/시간기반 CCDi -> REST -> REST. 단, capacity ref가 있으면 DOD 방전 부분만 CYCMRK -> CCDi_DOD -> REST -> LOOP(1) |
| `charge` | CYCMRK -> CCCV 또는 CCCh -> REST -> LOOP(count) |
| `discharge` | CYCMRK -> CCDi -> REST -> LOOP(count) |
| `cycle` | CYCMRK -> charge -> REST -> discharge -> REST -> LOOP(count) |
| `rate_test` | 각 C-rate group마다 CYCMRK -> CCCh -> REST -> CCDi -> REST -> LOOP(group count) |
| `pulse_test` | 초기 CCCV -> REST 후, SOC point마다 SOC adjust loop와 pulse measure loop 생성 |

`capacity_check` expander는 discharge 후 rest step 번호를 `capa_ref_rest_step`으로 반환한다. `schedule_to_binary_blocks()`는 이를 `ctx["capa_ref_step"]` 및 `ctx["capa_ref_map"][block_id]`에 저장한다. 이후 `soc_setting`/`pulse_test`는 `_resolve_capa_ref()`로 명시 block id 또는 최신 capacity check 참조를 찾는다.

### 6.5 Capacity reference 동작

`_set_cap_flag(b, mode_byte, ref_step_num)`는 offset 496/497을 설정한다.

- `mode_byte = 0x01`: DOD capacity cutoff
- `mode_byte = 0x00`: 100% return 계열
- `ref_step_num`: 참조할 step 번호

`blk_ccdi_dod()`는 DOD percent를 offset 384에 기록하고 mode/ref를 설정한다. `blk_ccc_return()`은 DOD 100.0과 mode `0x00`을 써서 pulse 후 회복 충전에 사용된다.

## 7. 현재 블록 의미

### 7.1 `rest`

단일 휴지 블록이다. UI 기본값은 30분, 기록 주기 30초, 전압 변화 기록 10mV이다. 바이너리에서는 CYCMRK와 LOOP(1)로 감싸진다.

### 7.2 `capacity_check`

용량 기준을 만드는 블록이다.

구조:

1. CCCV charge
2. charge 후 rest
3. CC discharge
4. discharge 후 rest
5. LOOP(1, reset capacity)

discharge 후 rest step이 이후 DOD 기반 SOC 이동의 capacity reference로 저장된다.

### 7.3 `soc_setting`

목표 SOC로 이동하는 블록이다. 먼저 full charge/rest를 수행하고, capacity reference가 있으면 DOD discharge로 `100 - target_soc_percent`만큼 방전한다. reference가 없으면 `(100 - SOC) / c_rate * 3600`으로 시간 기반 방전 시간을 계산한다.

중요한 현재 한계: 전체 블록이 하나의 CYCMRK/LOOP로 일관되게 감싸져 있지 않다. reference가 있을 때 DOD discharge 부분만 loop로 닫히며, 초기 CCCV/rest와 마지막 stabilize rest는 loop group 밖에 남는다.

### 7.4 `charge`

충전 전용 블록이다. `charge_mode`가 `cccv`이면 CCCV, `cc`이면 CCCh step을 만든다. 이후 rest와 LOOP(count)가 붙는다.

### 7.5 `discharge`

방전 전용 블록이다. CCDi, rest, LOOP(count) 구조이다.

### 7.6 `cycle`

일반 charge/rest/discharge/rest cycle이다. charge는 CCCV 또는 CC mode를 선택할 수 있고, 전체가 CYCMRK/LOOP(count)로 감싸진다.

### 7.7 `rate_test`

`c_rates` 배열을 순회하며 각 group마다 CC charge, rest, CC discharge, rest, LOOP(count)를 생성한다. UI 요약은 rate sequence를 표시한다. 현재 table은 `c_rate`, `count`만 입력받고, expander는 `group.discharge_c_rate`가 있으면 사용하지만 UI에서는 별도 방전 C-rate 필드를 만들지 않는다.

### 7.8 `pulse_test`

HPPC 스타일 pulse test이다.

- 초기 CCCV full charge와 recovery rest를 만든다.
- SOC points는 `interval`이면 `100 - interval`부터 0 초과까지 내림차순, `specific`이면 지정 배열을 내림차순 정렬한다.
- 각 SOC point마다 SOC adjust loop를 만든다.
- 이어 측정 loop를 만든다: stabilize rest -> discharge pulse -> recovery rest -> optional return charge/rest -> LOOP(1)

중요한 현재 한계:

- 초기 CCCV/rest 구간이 CYCMRK/LOOP로 감싸져 있지 않다.
- `record_time_rest_s` 기본값과 UI 필드가 있지만 expander는 일반 rest 기록 주기로 `record_time_s`를 읽는다. `pulse_test` 기본값에는 `record_time_s`가 없으므로 대부분 30초 fallback이 쓰인다.
- `charge_c_rate` 기본값과 UI 필드가 있지만 초기 full charge current는 `soc_step_c_rate`로 계산된다.
- capacity reference가 없으면 `_resolve_capa_ref()`가 0을 반환해 DOD step의 ref step이 0이 될 수 있다.

## 8. Mermaid preview

`mermaid_gen.py`는 schedule JSON을 `flowchart TD` 문자열로 변환한다. 서버의 `/api/preview`가 이를 반환하고, 브라우저는 Mermaid.js `mermaid.run()`으로 렌더링한다.

각 block은 Mermaid subgraph로 표현되고, block 간에는 subgraph 연결선이 추가된다. 내부 step 구성은 실제 바이너리와 완전히 1:1은 아니고 설명용 preview에 가깝다. 예를 들어 `pulse_test`는 SOC point 전체를 상세히 펼치기보다 대표 흐름과 loop edge로 요약한다.

주의점:

- `COLOR_MAP`에는 `charge`, `discharge` 색상이 없어 기본 회색으로 표시된다.
- preview는 실제 `.sch` offset/loop/capacity reference 검증 도구가 아니다.

## 9. `.sch` import

`sch_reader.py`는 `.sch` 바이너리를 현재 UI schedule JSON으로 best-effort 변환한다.

### 9.1 Decode

- `detect_header_size()`는 1632 또는 1760 header를 후보로 보고 `(len(data) - header_size) % 612 == 0`인지 확인한다.
- `decode_header()`는 author/name/safety를 읽는다.
- `decode_step()`은 각 612-byte step을 kind 중심 dict로 변환한다.

지원 kind:

- `rest`
- `cccv`
- `cc_charge`
- `cc_discharge`
- `loop`
- `cycle_marker`
- `end`
- `unknown`

### 9.2 Grouping

`split_loop_groups()`는 CYCMRK와 LOOP를 기준으로 group을 만든다. END에서 중단한다. 이후 `group_to_blocks()`가 group 내부 content pattern을 현재 UI block으로 매핑한다.

지원되는 주요 pattern:

- `["rest"]` -> `rest`
- `["cccv", "rest", "cc_discharge", "rest"]` -> `capacity_check`
- `["cccv", "rest"]` 또는 `["cc_charge", "rest"]` -> `charge`
- `["cc_discharge", "rest"]` -> `discharge`
- `["cc_discharge", "rest", "cc_charge", "rest"]` -> discharge + charge split

지원되지 않는 pattern은 warning을 남기고 가능한 단일 charge/discharge/rest 블록으로 분해한다.

### 9.3 Import의 본질적 한계

현재 importer는 cycle, rate_test, soc_setting, pulse_test를 원래 고수준 블록으로 완전히 복원하지 못한다. loop group의 low-level step pattern을 단순 블록으로 매핑하는 구조라, 복잡한 DOD/capacity reference 흐름은 warning과 함께 charge/discharge/rest 조합으로 보존된다.

스모크 테스트에서 `capacity_check + soc_setting(cap ref) + cycle`을 export 후 import하면 다음 결과가 나왔다.

```text
bytes 13872, steps 20
import_blocks ['capacity_check', 'capacity_check', 'rest', 'charge', 'rest', 'discharge', 'rest']
warnings ["group 3: unsupported pattern ['rest', 'cccv', 'rest', 'cc_discharge', 'rest']"]
```

이는 `soc_setting`의 일부 step이 loop group 밖에 놓이고 다음 CYCMRK와 섞이는 현재 구조와 관련된다. 즉 `.sch` import는 사용자 편집 편의용 best-effort 기능으로 보는 것이 맞다.

## 10. 전류 재스케일 도구

`sch_current_rescaler.py`는 기존 `.sch` 파일의 전류 필드를 old/new capacity 비율로 곱해 C-rate를 보존하는 CLI이다.

변경 대상:

- CCCV charge current, offset 16
- CCCV CV cutoff current, offset 32
- CC charge current, offset 16
- CC discharge current, offset 16

변경하지 않는 대상:

- header safety limit current
- voltage
- duration
- capacity reference
- DOD

`collect_current_fields()`는 현재 전류 필드를 요약하고, `scale_current_fields()`는 `new_capacity_mAh / old_capacity_mAh` factor를 적용한 bytes와 변경 summary를 반환한다.

`sch_current_rescaler_gui.py`는 같은 기능을 tkinter GUI로 감싼다. 파일 선택, 출력 경로 선택, old/new capacity 입력, 원본 전류 보기, 변환 실행을 제공한다.

## 11. 의존성

### Python

- Flask
- 표준 라이브러리: `os`, `io`, `json`, `threading`, `webbrowser`, `struct`, `datetime`, `argparse`, `sys`, `tkinter`

### Browser/CDN

- Bootstrap CSS/JS 5.3.0
- Bootstrap Icons 1.10.5
- Sortable.js 1.15.0
- Mermaid 10

네트워크가 없는 환경에서는 CDN 자산이 로드되지 않아 UI 스타일/아이콘/drag/preview 일부가 깨질 수 있다.

## 12. 데이터와 단위

주요 단위 변환:

- UI voltage V -> `.sch` mV
- UI C-rate -> mA by `c_rate * cell_capacity_mAh`
- UI minutes/hours -> seconds
- `.sch` importer는 반대로 mV -> V, seconds -> minutes/hours, mA -> C-rate를 계산한다.

기본값:

- cell capacity: 100 mAh
- max voltage: 4.3 V
- min voltage: 0.0 V
- max capacity: 200 mAh 또는 cell capacity * 2
- max temp: 70 C
- record time: 대체로 30 s
- voltage change: 대체로 10 mV

## 13. 중요한 구현 세부사항과 리스크

### 13.1 LOOP semantics

`blk_loop()`는 offset 564에 항상 `1`을 쓴다. 실제 장비/뷰어에서는 LOOP가 앞쪽의 가까운 CYCMRK로 돌아가는 구조로 해석되는 것으로 보인다. 따라서 high-level block은 가능한 `CYCMRK -> ... -> LOOP`로 닫혀야 한다.

현재 `rest`, `capacity_check`, `charge`, `discharge`, `cycle`, `rate_test`는 이 원칙에 대체로 맞는다. 반면 `soc_setting`과 `pulse_test`의 초기 구간은 완전히 감싸져 있지 않다.

### 13.2 Frontend와 backend schema drift

프론트엔드 `BLOCK_META`가 사실상의 입력 스키마이고, 백엔드 expander는 같은 key를 `dict.get()`으로 읽는다. 별도 schema validation이 없으므로 key 불일치가 조용히 fallback 기본값으로 이어질 수 있다.

실제 예:

- `pulse_test.record_time_rest_s`는 UI에 있으나 `sch_core.expand_pulse_test()`는 `record_time_s`를 읽는다.
- `pulse_test.charge_c_rate`는 UI에 있으나 초기 full charge에는 `soc_step_c_rate`가 사용된다.
- `rate_test` expander는 group의 `discharge_c_rate`를 지원하지만 UI table은 입력하지 않는다.

### 13.3 Save/load filename safety

`api_save()`와 `api_load()`는 filename/path 정규화가 부족하다. `schedule_name` 또는 `filename`에 `../`가 들어갈 경우 `SAVE_DIR` 밖 접근 가능성이 있다. 로컬 도구라 영향 범위는 제한적이지만, 웹 서버로 노출할 경우 즉시 보완해야 한다.

### 13.4 Import fidelity

Importer는 low-level pattern matching 기반이라 고수준 블록 복원이 제한적이다. 특히 cycle/rate/pulse/SOC 관련 의미는 손실될 수 있다. import 후 export한 파일은 원본과 의미가 달라질 수 있으므로 UI에서 warning을 더 명확히 보여주는 것이 좋다.

### 13.5 테스트 부재

현재 정식 테스트 디렉터리는 없다. `project_archive/deprecated_scripts/`에 과거 검증 스크립트가 있으나 현재 CI나 자동 테스트로 연결되어 있지 않다. 바이너리 포맷 특성상 offset regression test가 특히 필요하다.

## 14. 검증 결과

실행한 검증:

```text
python3 -m py_compile battery_scheduler/app.py battery_scheduler/sch_core.py battery_scheduler/sch_reader.py battery_scheduler/mermaid_gen.py battery_scheduler/sch_current_rescaler.py battery_scheduler/sch_current_rescaler_gui.py
```

결과: 성공.

처음 시도한 `../.venv/bin/python`과 `python` 명령은 이 환경에서 없어서 실패했고, `python3`로 재실행했다.

추가로 `schedule_to_sch()`와 `sch_to_schedule()`를 이용해 간단한 export/import 스모크 테스트를 수행했다. 바이너리 step 생성은 정상 동작했지만, `soc_setting` 포함 스케줄은 import 시 unsupported pattern warning이 발생했다. 이는 현재 importer와 expander 구조상 예상 가능한 한계이다.

## 15. 개선 우선순위

1. `soc_setting` 전체를 명확한 CYCMRK/LOOP group으로 닫을지 설계하고 구현한다.
2. `pulse_test` 초기 full charge/rest 구간도 CYCMRK/LOOP로 감싸거나, charge 전용 블록과 조합하도록 구조를 단순화한다.
3. `pulse_test`의 `record_time_rest_s`, `charge_c_rate`, `rest_min` 등 UI 필드와 expander 사용 key를 정렬한다.
4. save/load filename path traversal 방어를 추가한다.
5. `.sch` offset regression test를 만든다. 최소한 각 block type별 step type sequence, 주요 offset 값, capacity reference step 번호를 검증해야 한다.
6. import 기능은 warning을 UI에 상세 표시하고, “완전 복원”이 아닌 best-effort임을 명확히 해야 한다.
7. CDN 의존 프론트엔드 자산을 로컬 vendor로 가져올지 결정한다.

## 16. 전체 결론

이 코드베이스의 중심은 `static/js/app.js`의 블록 기반 schedule JSON 생성과 `sch_core.py`의 deterministic binary writer이다. 구조는 작고 직접적이며, 각 블록 expander가 실제 `.sch` step sequence를 책임진다. `.sch` writer는 header/step offset을 직접 pack하는 방식이라 단순하지만, schema drift와 offset regression에 취약하다.

현재 생성 기능은 기본 charge/discharge/cycle/capacity check/rate test에는 비교적 일관된 CYCMRK/LOOP 구조를 갖고 있다. 반면 SOC/pulse 계열은 capacity reference, DOD, loop grouping이 복잡하고 일부 구간이 loop group 밖에 있어 importer와 장비 viewer에서 해석 차이를 만들 수 있다. 다음 개발의 핵심은 SOC/pulse의 step 구조를 명확히 닫고, 프론트엔드 필드와 backend expander 입력을 정렬하며, 바이너리 offset 테스트를 추가하는 것이다.
