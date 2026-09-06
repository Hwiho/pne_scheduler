# Gate C5 — PNE PC / 장비 스모크 체크리스트 (최적화된 단일 세션)

상태: **실험실 실행 대기**
선행 조건: C1–C4 (헤더, 컴파일러, 네이티브 라운드트립, ASSB 교차검증)

이 체크리스트는 `build` 결과물을 **장비 실행 가능**으로 표시하기 전에 반드시 통과해야
하는 장비 관문입니다. 아래 항목을 **최소 1대 PNE 호기**(가급적 PNE02)에서 기록하기
전까지 Gate C를 완료로 표시하지 **마세요**.

> **왜 파일이 바뀌었나:** 기존 스모크 파일(Rest→CC→END, 3스텝)은 충전만 검증했습니다.
> `schema/fields.py` / `planning/GATE_B_CORPUS_EVIDENCE.json` / PNE02 controlled-pair
> 9건을 전수 분석한 결과, **충전 전류·전압, 방전 전류·전압, CV cutoff, LOOP count/goto,
> 스텝별 샘플링 간격은 이미 개별적으로 reopen-verified** 상태였습니다 (아래 §0 표,
> 전체 근거는 [`GATE_C5_EVIDENCE_COVERAGE.md`](GATE_C5_EVIDENCE_COVERAGE.md) 참고).
> 남은 진짜 미확인 항목은 "이 모든 필드를 처음부터 새로 조립한 헤더 하나에 같이 넣었을
> 때도 CTSEditorPro가 문제없이 여는가" 하나뿐입니다. 그래서 새 조합 프로브 파일
> `smoke_writer_probe.sch`로 **한 번의 리오픈에** 방전 코드패스, LOOP 구성, 스텝별
> 독립 샘플링까지 같이 확인하도록 재설계했습니다. 향후 Formation/Cycle Life류 모듈을
> 위해 별도 물리 테스트를 또 하지 않아도 되도록 하는 것이 목적입니다.

## 0. 이미 데이터로 확정된 것 (다시 확인할 필요 없음)

| 필드 | 근거 |
|------|------|
| 충전 전류/전압 (fVref@16, mode_value@12) | `pne02-charge-current` reopen-verified |
| 방전 전류 (fVref@16) | `pne02-discharge-current` reopen-verified |
| 방전 종료전압 (fEndV@28) | `pne02-end-voltage` reopen-verified, 골든 5/5 fixture = 2500 mV |
| CV cutoff 전류 (fEndI@32) | `pne02-cv-cutoff` reopen-verified |
| Rest 시간 (fIref@20) | `pne02-rest-duration` reopen-verified |
| LOOP count/goto (@48/@52) | `pne02-loop-count`, `pne02-loop-goto` reopen-verified |
| 충전/방전 샘플링 간격 (record_time_s@340) | `pne02-sampling-interval`, `pne02-sampling-interval-discharge` 각각 reopen-verified |
| 바이트 오프셋 겹침 없음 | `schema.fields.validate_step_field_registry()` — 소프트웨어로 이미 0건 확인 |

이 항목들의 **값** 자체는 이미 장비에서 검증됐습니다. 남은 것은 이 값들을
**하나의 from-scratch 파일**에 동시에 넣었을 때의 조립 결과뿐입니다 — 그래서 필드별로
따로 여러 번 테스트할 필요가 없습니다.

## 준비 (Setup)

| 항목 | 값 |
|------|-------|
| 날짜 | |
| 작업자 | |
| PNE 호기 | 예: PNE02 |
| CTSPro / CTSEditorPro 빌드 | 예: CYCC-1004-S01-R004-N01 |
| 채널 / 프로파일 | |
| 프로젝트 | `example/smoke_writer_probe.schproj` |
| 출력 파일 | `example/smoke_writer_probe.sch` — 사전 생성됨, 3596→6044 bytes, 7스텝 |

## 절차

1. 사전 생성된 파일 사용을 권장합니다: `example/smoke_writer_probe.sch`
   (`0x10003` / 612, 헤더는 실제 랩 파일에서 복제 — §3 근거 문서 참고).
   다시 만들려면:
   ```powershell
   python -m pne_scheduler.tools.rebuild_smoke_sch_from_lab_header example/smoke_writer_probe.schproj
   ```
2. `smoke_writer_probe.sch`를 PNE PC로 복사합니다. **(주의)** 이전 파일
   (`smoke_rest_cc_end.sch`)이 이미 채널에 열려 있었다면, PNE PC의 옛 파일을 새 파일로
   덮어쓴 뒤 다시 여세요.
3. **CTSEditorPro**에서 엽니다 (1차: 저장만 수행; **셀에서 실행하지 마세요**).
4. UI 값을 스텝별로 확인합니다 (아래 표의 "기대값"과 정확히 일치해야 함):

| 스텝 | 종류 | 확인 항목 | 기대값 |
|------|------|-----------|--------|
| 공통 | 시험/공통 안전조건 | 용량 (0/.000 이면 안 됨) | **80** |
| 공통 | 시험/공통 안전조건 | Vmax / Vmin / 온도 | 4200 / 2500 / 70 |
| 1 | Cycle marker | — | 표시만 확인 |
| 2 | CCCV 충전 | 전류 / 전압 / CV cutoff | **8 mA** / **4.200 V** / **4 mA** |
| 2 | CCCV 충전 | 샘플링 간격 / ΔV | **30 s** / **20 mV** |
| 3 | Rest | 시간 / 샘플링 간격 | **50 s** / **25 s** |
| 4 | CC 방전 | 전류 / 종료전압 | **8 mA** / **2.500 V** |
| 4 | CC 방전 | 전압 제한(V-limit) 표시값 | **≈2.000 V — 정상** (cutoff 2.5V와 다른 필드; §1 근거 문서 참고, 오류 아님) |
| 4 | CC 방전 | 샘플링 간격 / ΔV / (있다면) SOC·DOD | **15 s** / **5 mV** / (선택) 40% |
| 5 | Rest | 시간 / 샘플링 간격 | **35 s** / **10 s** |
| 6 | LOOP | count / goto 대상 | **2** / **step 2 (충전으로 복귀)** |
| 7 | END | 존재 여부 | 존재 |

   충전과 방전 전류가 둘 다 8 mA로 같은 것은 의도된 설계입니다(같은 0.1C, 80 mAh 셀) —
   둘 중 하나라도 다르게 표시되면 그 자체가 버그 신호입니다.
5. CTSEditorPro에서 한 번 다시 저장하고, `compare_sch`용으로 **원본·재저장본 둘 다**
   보관합니다.
6. (선택) reopen이 정상으로 보이면, 열린 채널에서 실행을 2차로 진행합니다. 언제든
   중단 가능하며, 완주는 필수가 아닙니다 (0.1C이므로 완주 시 수 시간 소요).

## 결과

| 확인 항목 | 통과? | 비고 |
|-------|:-----:|-------|
| CTSEditorPro가 오류 없이 파일을 연다 | ☐ | 실질적으로 유일한 새 리스크 (§3 근거 문서) |
| 공통 안전조건 용량이 표시된다 (0 아님) | ☐ | 기대: 80 mAh |
| 충전 스텝 값이 표 대로 표시된다 | ☐ | 전류/전압/cutoff/샘플링 |
| 방전 스텝 값이 표 대로 표시된다 | ☐ | 전류/종료전압/샘플링 — 처음 물리 확인되는 코드패스 |
| DOD/SOC 40%가 표시되는가 (있다면) | ☐ | 선택 — 표시되면 `dod_percent` writer_ready 승격 근거로 기록 |
| LOOP count=2, goto=step2가 표시된다 | ☐ | from-scratch 빌드에서 처음 물리 확인 |
| END 스텝이 있다 | ☐ | |
| 재저장 시 무관한 필드가 깨지지 않는다 | ☐ | `compare_sch` JSON 첨부 |
| (선택) 채널 실행이 시작/진행된다 | ☐ | |

## 서명

| 역할 | 이름 | 날짜 |
|------|------|------|

완료 후 `planning/ROADMAP.md` §11 / Gate C5 진행 기록에 이 체크리스트 경로와
[`GATE_C5_EVIDENCE_COVERAGE.md`](GATE_C5_EVIDENCE_COVERAGE.md)를 함께 남기세요.
DOD/SOC 표시값처럼 "선택" 항목에서 새로 확인된 값은 `schema/fields.py`의 해당 필드
confidence를 올릴 근거로 기록해 두면 다음 게이트에서 재활용할 수 있습니다.

---

## 부록: 최소 파일로 되돌리고 싶다면

`smoke_writer_probe.sch`가 열리지 않거나 문제 원인을 좁혀야 할 경우, 이전의 최소
스모크 파일(`example/smoke_rest_cc_end.sch`, Rest→CC→END 3스텝)로 먼저 재현해
헤더 프레이밍 문제인지 새로 추가된 방전/LOOP 로직 문제인지 구분할 수 있습니다. 이
파일은 계속 저장소에 남아 있고 회귀 테스트(`tests/test_c6_tail_and_smoke.py`)로
보호됩니다.
