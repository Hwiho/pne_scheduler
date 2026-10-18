# Windows 오프라인 배포판 사용 안내

이 배포판은 **미서명 시험 배포판**입니다. 소프트웨어 검사를 통과한 후보이며,
CTSPro 또는 장비 실행 승인을 뜻하지 않습니다. 실제 Windows 알림 표시·절전 복귀,
실험실 보안 정책·백신·화면 배율 검사는 별도입니다.

## 받기와 실행

1. GitHub `pne-scheduler-ci`의 성공한 실행을 열고 Artifacts에서
   `PNE-Scheduler-Windows-x64-<커밋>`을 받습니다. Actions 로그인 권한이 필요할 수 있습니다.
   Artifact 보관 기간은 30일이며 정식 Release 게시와 구분합니다.
2. Artifact 안의 `PNE-Scheduler-Windows-x64-<커밋 앞 12자리>.zip`과
   `.zip.sha256`을 함께 보관합니다. 반입 전 기관 보안 정책에 따라 검사합니다.
3. ZIP을 **전체 압축 해제**한 후 `PNE-Scheduler/PNE-Scheduler.exe`를 실행합니다.
   `_internal` 폴더를 포함한 전체 폴더가 필요합니다. exe만 옮기면 안 됩니다.
4. Python, pip, Node, 브라우저, Flask, 인터넷, localhost 서버는 필요하지 않습니다.
   Windows x64 시험 대상입니다. ARM/32비트, 네트워크 공유 폴더 직접 실행은 인수 전입니다.

관리자 권한은 요구하지 않습니다. 서명이 없어서 Windows 또는 기관 정책이 실행을
차단할 수 있습니다. 보안 기능을 끄거나 우회하지 말고 관리자에게 검토를 요청하세요.
실행되지 않으면 `%USERPROFILE%\.pne_scheduler\logs\desktop.log`를 확인합니다.
`build-info.json`에 원본 커밋·빌드 도구 버전·서명 여부가 기록됩니다.

## 데이터와 업데이트

- 프로젝트는 사용자가 지정한 `.schproj`에 저장합니다. 웹에서 저장한 프로젝트도 열 수 있습니다.
- 기본 라이브러리·고온저장·복구는 `%USERPROFILE%\.pne_scheduler`에 남습니다.
  exe 폴더와 분리되어 있으므로 새 버전을 새 폴더에 압축 해제해도 이 데이터는 유지됩니다.
- 알림 실행기는 고온저장 탭의 버튼으로 **직접 시작**합니다. 같은 DB의 중복 실행은 차단합니다.
  PC가 꺼져 있으면 알림을 보낼 수 없고, 집중 지원/알림 정책에 따라 표시가 억제될 수 있습니다.
  로그인 자동 시작 등록, 자동 업데이트, 서비스 설치는 하지 않습니다.
- 업데이트/백업 전 고온저장 또는 데이터 관리 탭에서 **안전 종료 요청**을 누르고
  **안전 종료 확인** 또는 미실행/잠금 해제 상태를 확인하세요. 종료 요청됨은 종료 완료가
  아닙니다. 구버전/응답 없는 실행기는 잠금 파일을 지우지 말고 Windows 로그아웃 등으로
  실제 종료한 후 상태를 다시 확인하세요. 다른 앱이 해당 데이터를 편집 중이면 중지하세요.
- 이전 버전으로 돌아가려면 이전 프로그램 폴더를 이용하세요. DB 형식 변경이 포함된 경우
  이전 프로그램과의 호환성을 추정하지 말고, 업데이트 전 백업을 별도 경로에서 확인하세요.
- 프로그램 제거는 프로그램 폴더만 삭제합니다. 사용자 데이터는 자동 삭제하지 않습니다.
- 시험 데이터 분리: `PNE-Scheduler.exe --data-dir "D:\PNE 시험 데이터"`.

## 검증 백업과 새 폴더 복원 (웹·Tk 공통)

1. **데이터 관리 → 백업 내용 미리보기**: DB·알림 확인 이력·방법·자동 복구본을 확인합니다.
   현재 프로젝트는 체크 시 미저장 내용까지 포함합니다. 외부 `.schproj`는 따로 선택합니다.
   웹에서는 한 줄에 하나의 절대 경로, Tk에서는 프로젝트 선택 버튼으로 여러 파일을 지정합니다.
2. 존재하는 폴더 안의 **새 ZIP 절대 경로**를 지정하고, 구버전 앱/외부 편집기 쓰기 중지를
   확인한 후 **검증 백업 저장**을 누릅니다. 데이터가 바뀌면 다시 미리보기 해야 합니다.
3. **복원 전 검사**로 파일 해시·DB·형식을 검사한 후 **아직 없는 새 복원 폴더**를 지정합니다.
   원본/기존 폴더는 덮어쓰지 않습니다. 복원된 프로젝트는 `projects`, 복구 기록은 `recovery`,
   방법은 `library`에 있습니다. 복구본의 원래 저장 경로는 분리하여 원본 덮어쓰기를 방지합니다.
4. 복원 완료 후 앱을 종료하고 `PNE-Scheduler.exe --data-dir "D:\PNE 복원 데이터"`로 실행합니다.
   소스 Tk는 `python run_pne_scheduler.py --data-dir "..."`, 소스 웹은
   `python run_pne_scheduler_web.py --data-dir "..."`입니다. 기존 인스턴스를 종료한 뒤 실행하세요.
   웹의 브라우저 초안은 별도이므로 복원된 `projects/*.schproj`를 명시적으로 열어 주세요.
5. 복원된 알림은 일시 정지합니다. 고온저장 목록에서 일정·지연 알림을 확인/미룬 후
   **기존 알림 설정 재개**, 필요할 때 **Windows 알림 시작**을 별도로 누릅니다.
   전송 이력은 실제 표시/열람을 보장하지 않으며, 전송 직후 강제 종료 시 재시도될 수 있습니다.

원자료·SCH 출력·로그·키 파일·선택하지 않은 외부 프로젝트/웹 초안은 기본 제외합니다.
ZIP에는 시료명/경로 등의 개인정보가 포함될 수 있으며 **암호화되지 않습니다**.
신뢰할 수 있는 로컬 드라이브에 보관하세요. 심볼릭 링크 경로, 파일당 32 MiB/전체 128 MiB
초과 백업, 미래 스키마는 거부합니다. 열린 DB의 파일 하나를 직접 복사하는 방식은 사용하지 않습니다.

## 창 없는 자체 점검

```powershell
$app = Resolve-Path .\PNE-Scheduler.exe
$report = Join-Path $env:TEMP "pne-check-new.json"
$process = Start-Process $app -ArgumentList @('--self-test', ('"' + $report + '"')) -Wait -PassThru
$process.ExitCode
Get-Content $report -Encoding utf8
```

새 결과 파일 경로를 사용하세요. 기존 파일은 덮어쓰지 않습니다. 임시 데이터만 만들어
장비 기준 읽기, 프로젝트 저장/재열기, 방법 저장, 80/90 mAh 배치 전류,
분석용 SCH 생성/재파싱, 고온저장 보관/복원, 검증 ZIP→새 위치 복원·알림 정지를 검사하고 임시 데이터를 정리합니다.
네트워크 연결·서버 열기는 검사 중 차단합니다. 알림은 보내지 않습니다.
별도의 `--gui-self-test REPORT`는 실제 Tk 초기화를 수행하므로 사용 중인 PC에서는
실행하지 말고 별도 Windows 시험 세션에서만 사용하세요.

## 개발자 빌드와 검증 경계

Windows x64/Python 3.12의 커밋된 깨끗한 checkout에서:

```powershell
python -m pip install -e . -r desktop-build-requirements.txt
python tools/build_windows.py --output dist/windows
python tools/check_windows_bundle.py dist/windows/PNE-Scheduler-Windows-x64-<commit>.zip --reports dist/package-checks
```

출력 경로가 이미 있으면 빌드는 중단합니다. 임의 폴더를 지우거나 덮어쓰지 않습니다.
기본 CI·웹·Linux/Windows Tk 검사 성공 후에만 배포 빌드를 시작합니다.
압축 해제본을 한글/공백 경로로 옮기고 Python 경로·Tcl 환경변수를 제거한 새 프로세스에서
자체 검사와 실제 Tk 7탭 검사를 실행합니다. 성공한 ZIP만 Artifact로 게시합니다.
이 검사도 Windows 실험실 PC의 보안 정책·DPI·실제 알림 표시·장비 인수를 대체하지 않습니다.

설계 근거: [PyInstaller 운영 모드](https://pyinstaller.org/en/stable/operating-mode.html)
(Windows에서 Windows 배포판 빌드, one-folder 방식),
[windowed 실행 주의사항](https://pyinstaller.org/en/stable/common-issues-and-pitfalls.html)
(콘솔 스트림 없음, 실행 파일 경로와 Python 인터프리터 구분).

## 남은 인수 항목

- 서명 인증서·서명/배포 정책, 기관 백신·폐쇄망 반입 승인
- 실제 실험실 Windows 버전, 100/150/200% DPI, 다중 모니터
- 실제 알림 표시·절전 복귀·로그아웃·재시작, 실험실에서 안전 종료와 백업 복구 연습
- CTSPro에서 정확한 파일 해시의 조건 대조와 별도 장비 실행 승인
