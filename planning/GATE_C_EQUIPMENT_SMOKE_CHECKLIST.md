# Gate C5 — PNE PC / 장비 스모크 체크리스트

상태: **실험실 실행 대기**  
선행 조건: C1–C4 (헤더, 컴파일러, 네이티브 라운드트립, ASSB 교차검증)

이 체크리스트는 `build` 결과물을 **장비 실행 가능**으로 표시하기 전에 반드시 통과해야 하는 장비 관문입니다.  
아래 항목을 **최소 1대 PNE 호기**(가급적 PNE02)에서 기록하기 전까지 Gate C를 완료로 표시하지 **마세요**.

## 준비 (Setup)

| 항목 | 값 |
|------|-------|
| 날짜 | |
| 작업자 | |
| PNE 호기 | 예: PNE02 |
| CTSPro / CTSEditorPro 빌드 | 예: CYCC-1004-S01-R004-N01 |
| 채널 / 프로파일 | |
| 프로젝트 | `example/smoke_rest_cc_end.schproj` |
| 출력 파일 | `example/smoke_rest_cc_end.sch` — Rest → CC 충전 → END (사전 생성됨) |

## 절차

1. 사전 생성된 파일 사용을 권장합니다: `example/smoke_rest_cc_end.sch` (3596 bytes, `0x10003` / 612).  
   다시 만들려면:
   ```powershell
   cd c:\Users\LGES\Cursor
   python -m pne_scheduler build pne_scheduler/example/smoke_rest_cc_end.schproj -o pne_scheduler/example/smoke_rest_cc_end.sch --allow-experimental-output
   ```
2. `smoke_rest_cc_end.sch`를 PNE PC로 복사합니다.
3. **CTSEditorPro**에서 엽니다 (1차: 저장만 수행; **셀에서 실행하지 마세요**).
4. UI 값을 확인합니다:
   - **공통 안전조건**: 용량 **80 mAh** (비어 있으면 안 됨), Vmax/Vmin/온도
   - Step1 REST **60 s** (기록 간격 60 s)
   - Step2 CC 충전 **8 mA**, 전압/리밋 **4200 mV (4.2 V)**, end-I **4 mA**
   - Step3 END 존재
5. CTSEditorPro에서 한 번 다시 저장하고, `compare_sch`용으로 **원본·재저장본 둘 다** 보관합니다.
6. (선택) reopen이 정상으로 보이면, 열린 채널에서 Rest→CC→END 실행을 2차로 진행합니다.

## 결과

| 확인 항목 | 통과? | 비고 |
|-------|:-----:|-------|
| CTSEditorPro가 오류 없이 파일을 연다 | ☐ | |
| 공통 안전조건 용량이 표시된다 (0 아님) | ☐ | 기대: 80 mAh |
| Rest 시간이 올바르게 표시된다 | ☐ | |
| 충전 전류 / 전압이 올바르게 표시된다 | ☐ | |
| END 스텝이 있다 | ☐ | |
| 재저장 시 무관한 필드가 깨지지 않는다 | ☐ | `compare_sch` JSON 첨부 |
| (선택) 채널 실행이 완료된다 | ☐ | |

## 서명

| 역할 | 이름 | 날짜 |
|------|------|------|
| 작업자 | | |
| 검토자 | | |

완료 후 `planning/ROADMAP.md` §11 / Gate C5 진행 기록에 이 체크리스트 경로를 남기세요.
