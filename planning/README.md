# Planning & lab evidence

Index for policies, corpus reports, equipment registry, and roadmap.

---

## Start here

| Document | Purpose |
|----------|---------|
| [`USER_ACTION_ITEMS.md`](USER_ACTION_ITEMS.md) | **What you still need to do in the lab** |
| [`GUARDRAILS.md`](GUARDRAILS.md) | **경계 항목 한눈에 보기** — 증거 규율·쓰기 안전·상태 정직성·열린 항목 (ROADMAP 정본으로 연결) |
| [`PROJECT_STRUCTURE.md`](PROJECT_STRUCTURE.md) | Directory map, code rules, cleanup workflow |
| [`LAB_DATA_POLICY.md`](LAB_DATA_POLICY.md) | PNE##.zip only, per-unit layout, CTS build |
| [`ROADMAP.md`](ROADMAP.md) | SCH structure, gates, **§5.6 lessons checklist**, modular UX vision (§1.1 / §6.6) |
| [`LAB_CORPUS_REPORT.md`](LAB_CORPUS_REPORT.md) | **Generated** per-cycler zip analysis (human-readable) |

## Machine-readable data

| File | Purpose |
|------|---------|
| [`EQUIPMENT_CURRENT_RATINGS.json`](EQUIPMENT_CURRENT_RATINGS.json) | Official max current tiers |
| [`EQUIPMENT_REGISTRY.json`](EQUIPMENT_REGISTRY.json) | Per-unit corpus zip, layouts, CTS |
| [`PNE_UNIT_CORPUS.json`](PNE_UNIT_CORPUS.json) | Corpus scan output |
| [`PNE_UNIT_COMPARISON.json`](PNE_UNIT_COMPARISON.json) | Cross-unit diff output |
| [`GATE_B_CORPUS_EVIDENCE.json`](GATE_B_CORPUS_EVIDENCE.json) | Corpus-inferred 612-byte field evidence |
| [`GATE_B_CONTROLLED_PAIR_WAIVERS.json`](GATE_B_CONTROLLED_PAIR_WAIVERS.json) | Documented waivers for controlled-pair evidence gaps |
| [`GOLDEN_SEMANTIC_EXPECTATIONS.json`](GOLDEN_SEMANTIC_EXPECTATIONS.json) | Per-fixture expected field values used by `test_golden_semantic.py` |
| [`GATE_B_VALIDATION_REPORT.json`](GATE_B_VALIDATION_REPORT.json) | Repository readiness vs actual Gate B exit |
| [`Q_NOM_POLICY.json`](Q_NOM_POLICY.json) | Explicit writer vs inferred viewer capacity contract |
| [`GOLDEN_FIXTURES_LOCKED.json`](GOLDEN_FIXTURES_LOCKED.json) | Locked golden test paths |
| [`SCHEDULE_MDB_ANALYSIS.json`](SCHEDULE_MDB_ANALYSIS.json) | CTSEditorPro `Schedule.mdb` structure analysis (lab-only, optional `mdb` extra) |
| [`UNKNOWN_FILENAME_ANALYSIS.json`](UNKNOWN_FILENAME_ANALYSIS.json) | Unlabeled-schedule filename mining output |
| [`UNKNOWN_SCH_CATEGORIZATION.json`](UNKNOWN_SCH_CATEGORIZATION.json) | Categorization results for unknown schedules |

## Gate B / fixtures

| Document | Purpose |
|----------|---------|
| [`GOLDEN_FIXTURES.md`](GOLDEN_FIXTURES.md) | Selected golden fixtures & rules |
| [`GOLDEN_FIXTURE_INTAKE.md`](../example/gate_b_export/GOLDEN_FIXTURE_INTAKE.md) | Fillable intake form |
| [`EQUIPMENT_CTS_FROM_PPT.md`](EQUIPMENT_CTS_FROM_PPT.md) | CTSPro builds from lab PPT |

## Gate C

| Document | Purpose |
|----------|---------|
| [`STEP_TYPES_EXTENDED.md`](STEP_TYPES_EXTENDED.md) | OCV / Impedance / Pattern / Balance type codes + shared offsets |

## Gate D

| Document | Purpose |
|----------|---------|
| [`GATE_D_VERIFICATION.md`](GATE_D_VERIFICATION.md) | **Canonical verification method** (V1–V8) |
| [`GATE_D_VERIFICATION_AUDIT.md`](GATE_D_VERIFICATION_AUDIT.md) | Audit findings + remediation status |
| [`GATE_D_VALIDATION_REPORT.json`](GATE_D_VALIDATION_REPORT.json) | Latest machine exit report (`gate_d_passed`) |
| `validate/gate_d_harness.py` | Module validate→expand→compile→parse harness |
| `validate/gate_d_verification.py` | Matrix-driven V1–V8 suite |
| `validate/topology.py` | Step-type family compare vs golden fixtures |
| `tests/test_capacity_contract.py` | Writer Q_nom vs viewer inference (L7) |
| `tests/test_gate_d_harness.py` | All P0/P1 module pipelines |
| `tests/test_gate_d_fixture_topology.py` | Golden family topology |
| `tests/test_gate_d_verification.py` | Runs verification method + audit remediations |

## Gate E

| Document | Purpose |
|----------|---------|
| [`UI_UX_NOTES.md`](UI_UX_NOTES.md) | Prior-art review of unmerged UI branches + Nova/LabVIEW pattern recommendations |

## User & technical docs (`docs/`)

| Document | Purpose |
|----------|---------|
| [`../docs/README.md`](../docs/README.md) | CLI, protocol, resume (user guide) |
| [`../docs/GATE_B.md`](../docs/GATE_B.md) | Validation intake, ASSB, Q_nom |
| [`../docs/GATE_B_GENERATED.md`](../docs/GATE_B_GENERATED.md) | Auto-generated layout/parser annex |
| [`../docs/CURSOR_CLOUD.md`](../docs/CURSOR_CLOUD.md) | Cursor Cloud / WSL |

## Regenerate corpus report

```powershell
python tools/analyze_pne_unit_corpus.py    # JSON only
python tools/compare_pne_units.py          # JSON + LAB_CORPUS_REPORT.md
```

## Legacy (검증 완료 후 보관)

종료된 게이트의 증거·소비 완료된 일회성 분석물은 [`../legacy/`](../legacy/)로 옮겼습니다.
코드가 로드하지 않는 파일만 이동했으며, 이력은 git에 그대로 남아 있습니다.

| 문서 | 내용 |
|------|------|
| [`GATE_C_EQUIPMENT_SMOKE_CHECKLIST.md`](../legacy/planning/GATE_C_EQUIPMENT_SMOKE_CHECKLIST.md) | **C5 서명 기록** (PNE02, 2026-09-08) — Gate F2 리오픈 승인 기록의 원자료 |
| [`GATE_C5_EVIDENCE_COVERAGE.md`](../legacy/planning/GATE_C5_EVIDENCE_COVERAGE.md) | C5 프로브 설계의 필드별 증거 감사 |
| [`SCH_696_TAIL_ANALYSIS.md`](../legacy/planning/SCH_696_TAIL_ANALYSIS.md) / [`.json`](../legacy/planning/SCH_696_TAIL_ANALYSIS.json) | 696바이트 tail 전수 조사 (결론은 writer 정책으로 반영됨) |
| [`SCH_LAYOUT_TIER_SHARING.md`](../legacy/planning/SCH_LAYOUT_TIER_SHARING.md) / [`.json`](../legacy/planning/SCH_LAYOUT_TIER_SHARING.json) | 500 mA vs 20 A 레이아웃 비교 |
| [`PNE04_UNKNOWN_REVIEW.md`](../legacy/planning/PNE04_UNKNOWN_REVIEW.md) / [`.json`](../legacy/planning/PNE04_UNKNOWN_REVIEW.json) | PNE04 미분류 스케줄 검토 |
| [`ENSOL_SCH_MAKER_ADOPTION.md`](../legacy/planning/ENSOL_SCH_MAKER_ADOPTION.md) | Ensol 오프셋 도입 이력 |
| [`../legacy/reports/`](../legacy/reports/) | 참조 0건인 일회성 분석 출력 3건 |
