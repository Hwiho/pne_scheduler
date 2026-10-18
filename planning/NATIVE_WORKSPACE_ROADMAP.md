# 오프라인 Tk · 웹 동등 기능 로드맵

기준일: 2026-10-18. v2 개선과 함께 게시하는 구현·로컬 검증 기록.

## 설계 재검토와 선택

실험실 PC에서 브라우저, Node 설치, localhost 서버 또는 네트워크를 사용할 수
없어도 프로젝트 작성과 파일 생성이 가능해야 한다. 웹 화면을 Tk 안에 띄우는
방식은 이 제약을 해결하지 못하므로 사용하지 않는다.

`웹 → HTTP 어댑터 → 공통 작업 함수 ← NativeController ← Tk`

- `api/routes.py`는 Flask 없는 Python 작업 함수다. Tk가 직접 호출한다.
- 프로토콜 계산, 단위 파싱, 시간 추정, 검증, 배치 전류 및 SCH writer를 복제하지 않는다.
- 양쪽은 같은 `.schproj`, 방법 라이브러리, SQLite 고온저장 데이터를 사용한다.
- Tk만의 작업 이력·자동 복구는 기존 `ProjectDocument`를 재사용한다.
- 프로젝트와 복구 저장은 같은 파일시스템의 임시 파일을 완전히 기록한 뒤 교체한다.
  디스크/교체 실패 시 이전 파일을 유지하고, 자동 복구 실패 시 문서 전환·종료를 차단한다.
  저장 성공 뒤 복구본 정리만 실패한 경우 저장 자체를 실패로 오표시하지 않는다.
- 긴 계산/파일 작업은 단일 작업 스레드, Tk 위젯은 메인 스레드에 한정한다.
- 기능 동등성이 목표다. 브라우저의 모바일 배치·드래그 제스처를 그대로 모사하지
  않으며 Tk는 데스크톱 세로 박스 + 이동 버튼 + 크기 조절 분할창을 제공한다.

## 이번 구현 범위

| 기능 | Tk 연결 | 유지할 일치 기준 |
|---|---|---|
| 셀·장비 설정 | 직접 기준용량, 전압, 전류 제한, 장비 선택 | 동일 C-rate → mA 변환과 장비 제한 |
| 프로토콜 조합 | 기본 CC/CCCV/방전/휴지/OCV, 실험 프리셋, 목적 검색 | 같은 기본값·스텝 순서 |
| 세로 박스 편집 | 추가·선택·복제·이동·삭제, 그룹·반복·그룹 해제 | 그룹의 자식 조건과 반복 보존 |
| 상세 편집 | 펼치기·큰 보기, 프리셋 분리, 개별 스텝 추가·편집·이동 | 동일 형태의 사용자 편집본과 LOOP 검증 |
| 수치 입력 | 숫자 + 선택 단위, SOC 0–100%, 입력 도움말 | 표시 단위 변경만으로 프로토콜 수정 금지 |
| 실험 도구 | 사이클+RPT, 단일 DC-IR, QC 연동, 기간 계산, QPEED 결과 선택 | 공통 preview/apply, 시간 추정의 불확실성 유지 |
| 방법 라이브러리 | 이름 저장, 버전 비교·선택, 검토 후 추가·교체 | 셀/장비 보존, 오래된 미리보기 차단 |
| 파일 생성 | 초안, 미리보기, SCH 검토 후보, 셀별 용량·C-rate 배치 | 동일 게이트·파일·manifest, 덮어쓰기 차단 |
| 기존 SCH | 설명, 허용 필드 편집 미리보기, 분석용 복사본 | 원본 해시 보존, 미검증 720 형식 읽기 전용 |
| 고온저장 | 기록·검색·필터·확인·미루기·완료·보관/복원·이력 | 같은 SQLite와 알림 실행기, 완료 후 경과시간 고정 |
| 프로젝트 수명주기 | 열기·저장·다른 이름·undo/redo·자동 복구 | 웹 저장 파일 왕복, 원본/복구 기록 보호 |

Tk에서 다른 프로젝트 열기/새 프로젝트는 새 문서의 undo 이력을 시작한다.
이전 미저장 프로젝트는 복구 목록에 남긴다. 웹의 문서 교체 undo와 이 차이는
확인창과 README에 명시하며 저장 경로가 잘못 연결되는 자동 undo는 제공하지 않는다.

## 실행 순서와 종료 기준

1. **N1 공통 처리 경계 — 로컬 구현**: SCH patch도 HTTP handler 밖으로 이동.
   Flask import와 소켓을 막은 상태에서 네이티브 편집·저장 테스트 통과.
2. **N2 네이티브 화면 — 로컬 구현**: 6탭과 위 기능 연결. 원본 데이터와 분리한
   테스트 디렉터리 지원. 숫자 입력 뒤 Enter/적용이라는 명확한 확정 동작 제공.
3. **N3 회귀 검증 — 로컬 검증 / CI 정의 추가**: 웹과 동일 프로젝트·스텝·SCH
   바이트 확인, 실제 Tk 위젯 테스트, 파일 생성/재읽기·undo·복구 테스트.
   Windows/Linux 네이티브 CI는 화면이 없으면 성공으로 건너뛰지 않게 설정.
   CI 정의 추가와 원격 실행 성공은 구분한다.
4. **N4a 시험 배포 준비 — 구현, 원격 빌드 확인 대상**: Python/Tcl/Tk를 포함한
   미서명 Windows x64 one-folder ZIP, 출처 커밋/해시와 명시적 자원 목록,
   Python 경로 없는 한글 경로에서 압축 해제본 자체 검사와 Tk 검사 후 Artifact 게시.
   사용자 데이터는 기존 홈 폴더에 보존하고 frozen 실행기의 알림 진입점을 분리한다.
   [Windows 안내](WINDOWS_OFFLINE_GUIDE.md)를 따른다.
   **N4b 실제 Windows 인수 — 미완료**: 서명, 폐쇄망 반입/백신, 높은 DPI/다중 모니터,
   실제 알림·절전·재부팅·로그인 시 실행 선택을 검증한다.
5. **N5 대형 실험과 결과 추적 — 후속 계획**: 수백 모듈의 가상화 목록, 배치 작업
   진행률/완료 이력과 재시도, 내보내기 결과 검색. 취소는 원자적 staging 경계에서만.
6. **N6 실측 용량 계보 — 샘플 필요**: 활성화/derating 실제 파일의 열·단위와
   셀/로트 매칭 검토 후 선택 적용. 직접 입력 기준용량이 계속 기본이다.

N4 이후를 소프트웨어 테스트만으로 완료 처리하지 않는다. 실측 샘플이나 사용자
실험 정책 없이 자동 매칭, 실험 조건 변경, 장비 승인을 추정하지 않는다.

## 검증 방법과 제한

- `tests/test_native_controller.py`: 기본 프리셋 결과 일치, 그룹 자식/스텝 편집,
  저장 왕복, 복구, 라이브러리 버전, 셀별 실제 전류, stale token, SCH 바이트/원본 보호.
- `tests/test_native_tk.py`: 실제 위젯 생성·입력·버튼·단위·탭·작업 스레드.
- `tests/test_native_protocol_dialogs.py`: 도구 입력과 미리보기 사이의 stale 상태 방지.
- macOS의 별도 Python 3.12/Tcl-Tk 9.0.4에서 네이티브 검증한다. 과거 Anaconda
  Python의 Tk 초기화 중단과 구분하며, 이를 이유로 새 GUI 검사를 생략하지 않는다.
- 자동 생성 SCH는 **CTSPro 재열기 검토 후보**다. 실제 CTSPro/장비 검증이 아니다.
- UI 구현·검증, Windows 실제 알림, 원격 Git/CI, 장비 인수는 별개의 완료 상태다.

## 이번 로컬 검증 결과

| 항목 | 결과 |
|---|---|
| 비-GUI Python 전체 | 950 passed, 1 skipped (비공개 샘플) |
| 실제 Tk 위젯·도구 대화상자·기존 Tk 통합 | 56 passed, 별도 실행 |
| 웹 | 22 passed, TypeScript 검사·배포 빌드 통과 |
| 정적 검사 | Ruff·diff whitespace 검사 통과 |
| 동일 결과 | 웹/Tk의 동일 SCH 바이트, 원본 보호 패치, .schproj 왕복 확인 |
| 실제 QA 산출물 | 기준용량 80/90 mAh 셀 2개 배치 7파일, 14스텝 검토 후보 묶음 5파일 |
| 화면 갱신 | 작은 창 줄바꿈의 geometry feedback 수정 후 너비 검사 1.25초 통과 |

Python 수치는 비-GUI와 Tk를 **분리 실행한 결과**다. 사용자 작업을 방해하지 않도록
최종 단계에서 새 창을 여는 재검사는 중단했고 테스트 창/실행 프로세스 잔류 없음도
확인했다. 전체 테스트의 GUI 구간은 숨김 root라도 macOS에서 앱 활성화가 발생할 수
있으므로 사용 중인 화면에서는 다시 실행하지 않는다. 이후 시각 검사는 사용자 확인
후 진행하거나 CI의 별도 디스플레이에서 수행한다. Windows CI 정의는 추가했지만
원격 실행 결과·실제 Windows 토스트·장비 인수는 아직 확인하지 않았다.

2026-10-18 사용자 요청에 따라 기존 v2 후속 변경과 함께 커밋·게시한다.
게시 전 재검사는 창 없는 테스트만 수행하며, 원격 CI·Windows 실기·장비 승인은
위 로컬 검증 결과와 별도로 확인해야 한다.

## Windows 초기화·배포 후속 — 2026-10-18

- `ac9a804` 원격 CI: 웹·Python·Linux native 성공. Windows native는 71 passed,
  1 error (`test_input_change_invalidates_preview_until_replanned[qc]`의 fixture에서
  `tk.Tk()` → `invalid command name "tcl_findLibrary"`). QC 기능 코드 실행 전 오류다.
  로그만으로 Windows OS/GC 등의 더 낮은 수준 원인을 확정하지 않는다.
- Tcl과 Tk 초기화를 분리하고 Windows에서 **현재 Tcl의 auto.tcl**에 정의된
  library finder를 명시적으로 준비한다. 환경변수나 다른 Python 설치를 추정하지 않는다.
  관련 근거: [Tcl auto.tcl](https://github.com/tcltk/tcl/blob/core-8-6-branch/library/auto.tcl).
  파손된 라이브러리는 실패로 남기며 재시도/skip으로 성공을 만들지 않는다.
- 화면 종료 전에 작업 스레드를 합류시키고 결과 큐를 정리한다. GUI 테스트도 같은
  초기화 함수를 사용하며 30회 반복 root 생성, Windows 전체 native 2회 연속 통과를 요구한다.
- 사용자 작업 중인 macOS에서는 GUI 재검사를 하지 않는다. 창 없는 초기화 단위 검사,
  패키지 자체 검사, 전체 비-GUI 회귀 검사 후 커밋·푸시하고 원격 결과를 확인한다.
- 배포의 남은 경계는 N4b다. 서명·보안 우회, 자동 실행 등록, 정식 GitHub Release,
  장비 승인은 이번 준비에 포함하지 않는다.
- 게시 전 로컬 결과: 비-GUI 961 passed / 비공개 샘플 1 skipped, 웹 22 passed,
  TypeScript·Ruff·diff 검사 통과. wheel을 별도 환경에 설치하고 checkout 밖에서
  `python -I -m pne_scheduler.desktop --self-test ...` 통과. Windows 실행 파일 및
  GUI 결과는 해당 커밋의 원격 Actions 실행으로 확인한다.
- 강화한 30회 반복 검사에서 `cfc1486`은 Tcl 자체의 `init.tcl` 읽기 오류
  (`couldn't read file ...: No error`)도 재현했다. 따라서 finder 준비만으로는
  충분하지 않다. pytest의 기본 OS 파일 디스크립터 교체 대신 `--capture=sys`로
  Python 출력만 수집한다. Windows Tcl 채널/pytest fd capture 충돌의 선행 사례:
  [ttkbootstrap 설정](https://github.com/israel-dryer/ttkbootstrap/blob/master/pyproject.toml),
  [pytest 수집 모드](https://docs.pytest.org/en/stable/how-to/capture-stdout-stderr.html).
  실패한 반복 검사를 제거/건너뛰지 않고 그대로 두 번 연속 실행한다.
- `fbde802`에서 Windows native **73 passed를 두 번 연속** 확인했다(원격 실행
  `39124670075`). 실행 파일 빌드는 성공했지만 압축 해제본 검사에서 SQLite 연결이
  닫히지 않아 Windows `WinError 32`가 재현되어 Artifact 게시를 차단했다.
  `sqlite3.Connection`의 with문은 close가 아니므로 작업/오류/초기화 실패 모두
  finally에서 연결을 닫도록 수정하고, GC와 무관한 연결 해제·rollback 회귀 검사를 추가한다.
