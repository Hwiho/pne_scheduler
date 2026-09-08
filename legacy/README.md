# legacy — 검증이 끝난 자료 보관소

여기 있는 파일은 **삭제 대상이 아니라 보관 대상**입니다. 각자 맡은 판단을 이미
내렸고, 그 결론이 코드·정책·로드맵에 반영된 자료들입니다.

## 이동 기준

옮긴 것:

- 종료된 게이트의 증거 문서 (Gate C5)
- 결론이 이미 정책으로 흡수된 일회성 분석물 (696 tail, 레이아웃 티어 비교 등)
- 참조 0건인 분석 출력물

옮기지 않은 것:

- **코드·테스트가 런타임에 로드하는 파일** — `planning/*.json` 다수가
  `schema/equipment*.py`, `tests/golden_fixtures.py`, `test_capacity_contract.py`,
  `test_golden_semantic.py`, Gate B/D 검증기에서 경로로 직접 읽힙니다
- 현재 진행 중인 게이트의 문서 (Gate D 검증 방법론, Gate E UI 노트 등)
- 살아있는 정책 문서 (`LAB_DATA_POLICY.md`, `Q_NOM_POLICY.json`, `GUARDRAILS.md` 등)

이동 시점에 `.py` 참조가 0건임을 확인했고, 이동 후 308개 테스트와
Gate B/D 검증이 모두 통과함을 확인했습니다.

## 주의 — 이 자료들은 여전히 증거로 인용됩니다

`legacy/`에 있다고 해서 "더 이상 유효하지 않다"는 뜻이 **아닙니다.** 특히:

| 파일 | 왜 아직 중요한가 |
|------|------------------|
| `planning/GATE_C_EQUIPMENT_SMOKE_CHECKLIST.md` | PNE02에서 서명된 **C5 통과 기록**. Gate F2(리오픈 승인 기록)가 요구하는 원자료이며, 릴리스 시 정확한 아티팩트 해시와 함께 다시 인용해야 합니다 |
| `planning/GATE_C5_EVIDENCE_COVERAGE.md` | C5 프로브가 왜 그 필드 조합으로 설계됐는지의 근거. 추후 장비 재검증 범위를 정할 때 재사용됩니다 |
| `planning/SCH_696_TAIL_ANALYSIS.*` | writer가 696 tail을 0으로 채우는 **현행 정책의 근거**. nonzero tail이 발견되면 이 조사부터 다시 봐야 합니다 |

## 구조

```
legacy/
├── planning/   종료된 게이트 문서 + 소비 완료된 분석물
└── reports/    참조 0건 일회성 분석 출력
```

정본 색인은 [`../planning/README.md`](../planning/README.md), 게이트 상태는
[`../planning/ROADMAP.md`](../planning/ROADMAP.md)입니다.
