# What you need to do (lab / decisions)

Gate C **exited 2026-09-08** (C5 PNE02). Gate D **software exit 2026-09-08**
(capacity contract + all P0/P1 module harnesses + golden family compares).
Software focus is now **Gate E** plus the pattern-acceptance track. Immediate user work is
not required until the SOC/DOD controlled-pair session or the generated reopen pack is ready.

---

## 1. Gate C5 — ✅ done

Checklist: [`GATE_C_EQUIPMENT_SMOKE_CHECKLIST.md`](../legacy/planning/GATE_C_EQUIPMENT_SMOKE_CHECKLIST.md)

---

## 2. Gate D — ✅ software done

- Capacity contract: `tests/test_capacity_contract.py`
- Module pipelines: `tests/test_gate_d_harness.py`
- Golden families: `tests/test_gate_d_fixture_topology.py`

Honest gaps (no lab required to close Gate D software bar): DCR IR-only;
`fEndC` unverified; modules are templates ≠ full lab schedules.

---

## 3. Next coordinated lab checkpoint — SOC/DOD first

This checkpoint runs before HPPC/QPEED/RPT/DCIR reopen candidates are approved. Full plan:
[`PATTERN_VALIDATION_PLAN.md`](PATTERN_VALIDATION_PLAN.md) §4/§6.

### 3.1 필수 pair 두 개

1. **Pair A — DOD/SOC percent:** 조건을 두 파일 모두 켜고 값만 `30% → 40%`
2. **Pair B — capacity cutoff:** 조건을 두 파일 모두 켜고 값만 변경
   (80 mAh 기준이면 `24 mAh → 32 mAh`; UI가 %를 받으면 `30% → 40%`)
3. 각 pair의 before/after와 CTSEditorPro 재저장본 보관
4. `compare_sch`로 `@384`와 `fEndC@36`을 서로 별도로 확인

off/on은 enable/cap-reference flag도 함께 바꿀 수 있으므로 필요할 때 보조 pair로 추가한다.

### 3.2 왜 두 pair가 필요한가

C5에서 프로브의 `dod_percent`=40%가 **CTSEditorPro UI에 나타나지 않았다**
("확인 못함"). Gate C는 선택 항목이라 통과했지만 원인이 미확정이다:

- (a) 그 스텝 타입에 DOD 입력 칸이 없음
- (b) 우리 오프셋(`@384`)이 틀림
- (c) 다른 화면/탭에 있음

Smoke probe, HPPC full, QPEED 후보는 `dod_percent → @384`를 쓰고,
`dcir/hppc:legacy/rpt`는 `end_capacity_fraction → fEndC@36`을 쓴다. HPPC full/QPEED에는
Pair A, legacy HPPC/RPT/DCIR에는 Pair B가 직접 필요하므로 batch 전체를 승인하려면 둘 다 필요하다.

그때까지: `dod_percent`는 `corpus_inferred`, `fEndC`는 `semantic_unverified` 유지;
둘 다 근거 없이 `writer_ready`로 승격하지 않는다. SOC-dependent pattern은
`prototype/software-checked`까지만 허용한다.

### 3.3 같은 세션의 선택 항목 — extended step types

CTS Type dropdown의 **Ocv / Impedance / Balance / Pattern** stubs는
[`STEP_TYPES_EXTENDED.md`](STEP_TYPES_EXTENDED.md)에 있고 현재 example fixture는 0개다.
시간이 허용되면 Rest→각 type→END controlled pair를 Pair A/B와 함께 만든다.

---

## 4. Optional / later

| Item | When |
|------|------|
| Nonzero 696 tail appears | Controlled pair |
| OCV/Imp/Balance/Pattern pairs | §3.3 |
| Prefer `patch-sch` for production edits | Until CLI header 54-byte gap understood |

---

## 5. Software next

- **Gate E** — Nova + LabVIEW *feel* for module/procedure authoring (§1.1, §6.6)
- **Pattern acceptance PV0–PV3** — canonical recipe를 만든 뒤 reopen pack 생성
- **PV3 pack 준비됨:** [`../example/pattern_review_pack/2026-09-09/INDEX.md`](../example/pattern_review_pack/2026-09-09/INDEX.md).
  사용자는 `REOPEN_ONLY_DO_NOT_RUN` 파일을 CTSEditorPro에서 일괄 reopen하고
  `review_results.csv`에 기록한다. RPT 및 family-template 후보는 특히 prototype/근사 recipe로 본다.
- Do not invent DCR binary maps without evidence
- Do not claim full 696 semantic lab parity beyond framing/zero-tail policy
