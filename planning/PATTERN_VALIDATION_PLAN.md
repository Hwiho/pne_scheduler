# Pattern Acceptance Plan — HPPC / QPEED / QC / Cycle 일괄 검증

작성: 2026-09-08
목적: 구현된 모듈이 단순히 파일로 써지는 수준을 넘어, 실제 랩 패턴과 맞고
CTSEditorPro에서 의도대로 보이는지 **적은 횟수의 사용자 검증으로** 확인한다.

---

## 1. 결론

여러 패턴을 한 번에 만들고 사용자가 CTSEditorPro에서 묶어서 검증하는 방식이 좋다.
한 파일씩 개발→확인하는 왕복보다 빠르고, 모든 결과를 같은 장비/CTSPro 조건에서 비교할
수 있다.

Gate D의 자동 검증은
`validate → expand → compile → parse`와 step **family**를 확인했을 뿐, 원본 랩 패턴의
step 수·순서·조건을 복제했다는 뜻이 아니다. 먼저 corpus/golden을 기준으로 recipe를
정확히 만든 뒤 검증 pack을 생성한다.

검증은 다음 두 단계로 분리한다.

1. **CTSPro reopen 검증:** 파일 열기, 표시값, 저장, 원본/재저장 diff
2. **장비 run 검증:** 별도 승인된 최소 대표 파일만 dummy cell/안전 조건으로 시작·중단

첫 사용자 전달 pack은 **reopen 전용**이다. 파일을 열어 보는 것과 실제 셀에서 실행하는
것을 같은 승인으로 취급하지 않는다.

---

## 2. 현재 구현을 다시 점검한 결과

| 패턴 | 현재 상태 | 실제 근거와 차이 |
|------|-----------|------------------|
| Formation | 짧은 반복 template | golden은 7/9/13/19-step variant가 있음 |
| Cycle life / in-situ | 7-step 기본 loop template | corpus는 17/25/31/41/73-step 등 여러 variant; 중간 RPT/checkpoint 여부 미모델링 |
| capacheck / derating | family 수준 template | golden 순서/loop 구조와 완전 일치하지 않음을 코드도 명시 |
| QC | `cycle`/`1n1q`/`1_charge` 구현, 17/18/24–26 step shape 검사 | Set별 화면값과 variant 의미는 reopen 확인 필요 |
| HPPC | `full` 62-step topology + legacy SOC pulse variant | DOD와 5.0/2.2 V CC mode-limit 표시 의미는 reopen 확인 필요 |
| QPEED full | golden topology 기반 167-step 구현 | DOD/cap-reference 의미와 표시값은 reopen/controlled pair 필요 |
| QPEED SOC setting | golden topology 기반 11-step 구현, LOOP reference resolve | `DOD@384` 의미는 PV1 전까지 미승인 |
| RPT / DCIR | SOC ladder template | `fEndC@36` 의미 미검증, DCR window는 binary에 쓰지 않음 |

따라서 생성된 pack은 곧바로 실행하는 파일 묶음이 아니라 **canonical expectation을
화면에서 대조하기 위한 reopen 전용 후보**다.

### 2.1 2026-09-09 소프트웨어 진행 결과

- Composer가 module-local LOOP를 전체 step 번호로 재배치하고 최종 END를 하나만 만든다.
- HPPC full 62-step, QPEED full 167-step / SOC-setting 11-step, QC 3종을 구현하고
  locked topology 자동 검사를 추가했다.
- catalog의 trust/variant/제약과 구조화 preflight를 UI flow model과 공유한다.
- PNE02 lab header를 사용하는 결정적 review-pack 생성기를 추가했다.
- 실제 후보 10종은
  [`../example/pattern_review_pack/2026-09-09/INDEX.md`](../example/pattern_review_pack/2026-09-09/INDEX.md)에 있다.

남은 핵심은 Formation/Cycle/capacheck/RPT family-template의 exact recipe 승격,
PV1 controlled pairs, 사용자의 PV4 batch reopen이다. HPPC는 step-type topology는
locked golden과 일치해 `software-checked`이며, 필드 의미 검증 전까지 reopen/run 등급으로
승격하지 않는다.

---

## 3. 승인 상태

| 상태 | 의미 | UI/사용 허용 |
|------|------|--------------|
| `prototype` | 아이디어/기본 topology만 구현 | Advanced에서만, export 차단 |
| `software-checked` | canonical expectation + compile/parse/diff 자동 테스트 통과 | 설계/preview, reopen candidate 생성 가능 |
| `CTSPro-reopen-candidate` | hash가 고정된 사용자 검증 대기 파일 | CTSEditorPro 열기/재저장만 |
| `CTSPro-reopen-verified` | 동일 hash가 대상 CTSPro에서 열리고 표시값/재저장 확인 | 해당 profile의 patch/reopen 근거 |
| `equipment-run-verified` | dummy cell/실장비 안전 절차로 실행 확인 | 정확한 recipe/hash/profile 범위에서만 실행 승인 |

한 패턴의 승인은 다른 패턴이나 변경된 hash로 자동 전파하지 않는다.

---

## 4. DOD/SOC 40%와 `fEndC` 검증 시점

**시점:** pattern acceptance의 첫 lab checkpoint(PV1), HPPC/QPEED/RPT/DCIR
reopen candidate를 확정하기 **전**에 한다. OCV/Impedance/Balance controlled-pair를
만드는 세션과 묶어도 되지만 SOC pair의 우선순위가 더 높다.

C5에서 확인하지 못한 `dod_percent=40`과 실제 모듈의 SOC cutoff는 같은 문제가 아니다.

- smoke probe, HPPC full, QPEED full/SOC-setting: `dod_percent` → compiler의 `@384`
- HPPC legacy/RPT/DCIR: `end_capacity_fraction` → compiler의 `fEndC@36`

따라서 controlled pair도 둘로 나눈다.

### Pair A — DOD/SOC percent

1. 동일한 방전 step 두 파일을 CTSEditorPro에서 만든다.
2. 두 파일 모두 해당 종료조건을 켠 채 DOD 또는 SOC percent만 `30% → 40%`로
   변경한다. off/on 비교는 enable flag까지 함께 바꿀 수 있으므로 보조 pair로만 쓴다.
3. 저장 후 `compare_sch`로 changed byte/field를 확인한다.
4. UI에서 다시 열어 40% 표시 위치와 단위를 기록한다.

목적: `@384`가 맞는지, 어떤 step/mode에서 표시되는지 확인.

### Pair B — capacity cutoff / SOC setting

1. 동일 방전 step 두 파일에서 capacity 종료조건을 모두 켠다.
2. 80 mAh 기준이라면 값만 `24 mAh(30%) → 32 mAh(40%)`로 변경한다. UI가 직접
   percent를 받으면 30%→40%로 기록한다. off/on은 enable/cap-reference byte를 찾는
   별도 보조 pair로 둔다.
3. changed byte가 `fEndC@36`인지, 저장 단위가 mAh인지 %인지 확인한다.
4. capacity reference step/actual-capacity flag가 같이 바뀌면 그 byte도 별도 evidence로 기록한다.

목적: HPPC legacy/RPT/DCIR의 SOC-setting이 사용하는 `end_capacity_fraction` 경로를 검증.

HPPC full/QPEED 승격에는 Pair A가, HPPC legacy/RPT/DCIR 승격에는 Pair B가 직접
필요하다. 패턴 batch 전체의 SOC 경로를 승인하려면 두 pair를 모두 확인한다.

---

## 5. 검증할 패턴 matrix

### P0 — 기본 제공 후보

| ID | Pattern / variant | 기준 fixture | 구현 전 확인할 핵심 |
|----|-------------------|--------------|----------------------|
| PV-FM | Formation variants | 7/9/13/19-step FM | cycle 수, SOC30 종료, rest/limit |
| PV-CAPA | capacheck / derating | 13/15/19/41-step | 0.1C→C/3, single/double C/3, loop 순서 |
| PV-QC-C | QC 1 charge | 24–26-step | 1C/C/3 구간, 종료조건, variant 차이 |
| PV-QC-NQ | QC 1N1Q | 17/18-step | 1N1Q 정확한 의미와 step 순서 |
| PV-QC-CYCLE | QC cycle | 17/18-step | QC_1N1Q와 동일/상이한 recipe인지 |
| PV-CYCLE | Cycle life | 17/25/31/41/73-step | 기본 cycle, checkpoint/RPT 삽입, loop 범위 |
| PV-HPPC | HPPC full range | 62-step PNE02 golden | SOC ladder, pulse 방향/폭/휴지, 반복 |
| PV-QPEED-F | QPEED full | 167-step PNE02 golden | HPPC와 다른 실제 pulse train 전체 |
| PV-QPEED-S | QPEED SOC setting | 11-step PNE02 fixture | SOC cutoff, loop target/count, cap reference |
| PV-RPT | RPT variants | 19/41-step | C/3와 DCIR pulse, SOC 지점, DCR 표시 |

### P1 — 기본기/선택

- standalone charge / discharge / rest
- rate capability
- DCIR-only
- OCV / Impedance / Balance / Pattern (controlled evidence가 생긴 타입만)

P0의 모든 variant를 억지로 하나의 module class에 넣지 않는다. 실제 절차가 다르면
별도 named preset/recipe로 유지하고 사용자가 선택하게 한다.

---

## 6. 실행 단계

### PV0 — Canonical extraction (software only)

- 각 기준 fixture의 step type, mode, I/V/time/end condition, LOOP 범위를 추출
- 동일 계열 fixture끼리 공통 skeleton과 variant 차이를 표로 만듦
- filename inference가 아니라 locked fixture + byte evidence를 출처로 저장
- 사용자에게 의미 확인이 필요한 항목은 `unknown`, `assumption`으로 분리

종료 기준: 각 P0 pattern마다 machine-readable expectation과 사람이 읽는 overview 존재.

### PV1 — SOC/DOD controlled pairs (첫 lab checkpoint)

- §4 Pair A/B 작성, reopen, before/after 보존
- 가능하면 같은 세션에서 OCV/Impedance/Balance (+ 사용 시 Pattern) pair 수집
- evidence를 `schema/fields.py`와 intake report에 반영

종료 기준: `@384`와 `fEndC@36`을 각각 승격하거나, 틀린 가정을 수정하고 차단 유지.

### PV2 — Recipe 구현과 자동 검증

- composer fragment/LOOP reference 계약을 먼저 적용
- QC 3종, QPEED 2종을 명시적인 variant로 구현
- HPPC/QPEED/Cycle/Formation/capacheck/RPT를 canonical expectation과 비교
- step family가 아니라 순서, step count, 중요 field, loop target까지 검사
- mutation/backtest로 일부 step/field를 깨면 반드시 실패하는지 확인

종료 기준: P0 recipe가 `software-checked`; 가정/미지원 필드는 manifest에 남음.

### PV3 — Reopen candidate pack 생성

한 번의 명령으로 다음 구조를 만든다.

```text
pattern_review_pack/<date>/
  INDEX.md                    # 파일 순서, 위험, 기대값
  review_results.csv          # 사용자가 pass/fail/비고 기록
  <pattern-id>/
    source.schproj
    candidate.sch
    candidate.sch.manifest.json
    expected_steps.csv
    expected_overview.md
    sha256.txt
```

Pack 규칙:

- 대상은 우선 PNE02 `0x00010003/612`; 다른 장비/layout은 별도 pack
- 모든 파일은 짧고 구분되는 sentinel 값으로 **표시 확인용** 생성
- 원본 lab header를 사용했다면 source hash와 수정 범위를 manifest에 기록
- `build_sch_header()`의 54-byte gap이 남아 있는 동안 일반 from-scratch release로 부르지 않음
- 파일명과 문서에 `REOPEN_ONLY_DO_NOT_RUN` 표시

종료 기준: pack 전체 internal parse/roundtrip, schema validation, hash 고정, 예상표 생성.

### PV4 — 사용자 batch reopen

권장 순서:

1. 가장 단순한 primitive/cycle 파일을 먼저 연다.
2. 각 파일의 step 수·순서·I/V/time/cutoff/LOOP를 `expected_steps.csv`와 비교한다.
3. Save As로 재저장하고 원본과 함께 보관한다.
4. `review_results.csv`에 pass/fail/화면 위치/자동 보정값을 기록한다.
5. 오류가 하나라도 있으면 실제 셀에서 실행하지 않는다.

종료 기준: candidate hash별 CTSPro build/PNE unit/operator 결과와 재저장 파일 확보.

### PV5 — Diff 반영과 최소 재검증

- candidate vs CTS 재저장본 diff 자동 분석
- CTS가 자동으로 채운 field와 잘못 쓴 field를 구분
- 실패한 pattern/공유 field만 수정
- 공유 compiler 수정이면 영향받는 pack 전체 자동 회귀, 물리 reopen은 영향 파일만 재수행

종료 기준: P0 패턴별 승인 상태 갱신; UI catalog badge와 동일.

### PV6 — 선택적 equipment run

- reopen pack 전체를 실행하지 않는다.
- primitive 조합, loop, SOC-dependent, pulse 계열에서 위험을 대표하는 최소 파일만 선택
- dummy cell, current/voltage 상한, 즉시 중단 기준, operator 서명을 Gate F에 기록

종료 기준: 정확한 candidate hash/profile만 `equipment-run-verified`.

---

## 7. 다른 Gate와의 관계

- Gate E의 셸/Procedure/폼/undo 작업은 PV0–PV5와 병행 가능
- Gate E의 기본 Module palette 승격은 해당 pattern의 PV2 결과 필요
- SOC-dependent 패턴의 reopen 승격은 PV1 Pair B 필요
- from-scratch Export를 일반 사용자에게 안전하게 보이게 하는 것은 PV4/PV5 이후
- Gate F의 최종 제품 release는 선택한 P0 범위의 PV5와 정확한 hash/profile 기록 이후
- OCV/Impedance/Balance, DCR window, 696 tail은 사용하지 않는 한 release 범위 밖으로
  명시적으로 제외 가능하며, 숨은 TODO로 남기지 않는다

즉, **나머지 Gate를 먼저 진행하는 것은 가능하지만, 패턴 의미와 composer 계약처럼 UI와
출력 구조를 바꾸는 미완성 항목은 마지막까지 미루지 않는다.** 반면 사용하지 않는 extended
type이나 696 nonzero tail처럼 격리 가능한 항목은 release scope 밖으로 두고 나중에 처리할
수 있다.
