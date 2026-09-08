# What you need to do (lab / decisions)

Gate C **exited 2026-09-08** (C5 PNE02). Gate D **software exit 2026-09-08**
(capacity contract + all P0/P1 module harnesses + golden family compares).
Software focus is now **Gate E** (modular UX). Below is only optional lab work.

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

## 3. Optional lab — extended step types

CTS Type dropdown includes **Ocv / Impedance / Balance / Pattern**. Stubs:
[`STEP_TYPES_EXTENDED.md`](STEP_TYPES_EXTENDED.md). Corpus samples: **zero**.

When spare PNE02 time:

1. Rest→OCV→END, Rest→Impedance→END, Rest→Balance→END (+ Pattern if used)
2. Save + reopen; keep before/after bytes for Gate B5 intake
3. Promote nonzero deltas into `schema/fields.py`

### 3.1 같은 세션에서 함께 처리할 것 — DOD/SOC (C5 미해결 승계)

C5에서 프로브의 `dod_percent`=40%가 **CTSEditorPro UI에 나타나지 않았다**
("확인 못함"). Gate C는 선택 항목이라 통과했지만 원인이 미확정이다:

- (a) 그 스텝 타입에 DOD 입력 칸이 없음
- (b) 우리 오프셋(`@384`)이 틀림
- (c) 다른 화면/탭에 있음

**필요한 것:** CTSEditorPro에서 **SOC 또는 DOD를 직접 입력한** 방전 스텝을 만들어
저장 → 그 값만 바꾼 두 번째 파일 저장 → before/after 바이트 비교(controlled pair).
그러면 (a)/(b)/(c)가 한 번에 갈린다. OCV/Imp/Balance 세션과 같이 하면 추가 비용이
거의 없다.

그때까지: `dod_percent`는 `corpus_inferred` 유지, **writer_ready 승격 금지**.
현재 이 필드를 쓰는 것은 `smoke_writer_probe` 뿐이고, 실제 실험 모듈
(dcir/hppc/rpt/qpeed)은 `fEndC`를 사용하므로 실사용 영향은 없다.

---

## 4. Optional / later

| Item | When |
|------|------|
| Nonzero 696 tail appears | Controlled pair |
| OCV/Imp/Balance pairs | §3 |
| Prefer `patch-sch` for production edits | Until CLI header 54-byte gap understood |

---

## 5. Software next

- **Gate E** — Nova + LabVIEW *feel* for module/procedure authoring (§1.1, §6.6)
- Do not invent DCR binary maps without evidence
- Do not claim full 696 semantic lab parity beyond framing/zero-tail policy
