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
- 업데이트/백업 전 작업실과 기존 알림 실행기를 종료하세요. 현재 알림 실행기는 별도 종료
  화면이 없으므로 Windows 로그아웃으로 확실히 종료할 수 있습니다. 열린 SQLite DB를
  파일 하나만 복사하지 말고, 종료한 뒤 `.pne_scheduler` 폴더 전체와 프로젝트를 백업하세요.
- 이전 버전으로 돌아가려면 이전 프로그램 폴더를 이용하세요. DB 형식 변경이 포함된 경우
  이전 프로그램과의 호환성을 추정하지 말고, 업데이트 전 백업을 별도 경로에서 확인하세요.
- 프로그램 제거는 프로그램 폴더만 삭제합니다. 사용자 데이터는 자동 삭제하지 않습니다.
- 시험 데이터 분리: `PNE-Scheduler.exe --data-dir "D:\PNE 시험 데이터"`.

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
분석용 SCH 생성/재파싱, 고온저장 보관/복원을 검사하고 임시 데이터를 정리합니다.
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
자체 검사와 실제 Tk 6탭 검사를 실행합니다. 성공한 ZIP만 Artifact로 게시합니다.
이 검사도 Windows 실험실 PC의 보안 정책·DPI·실제 알림 표시·장비 인수를 대체하지 않습니다.

설계 근거: [PyInstaller 운영 모드](https://pyinstaller.org/en/stable/operating-mode.html)
(Windows에서 Windows 배포판 빌드, one-folder 방식),
[windowed 실행 주의사항](https://pyinstaller.org/en/stable/common-issues-and-pitfalls.html)
(콘솔 스트림 없음, 실행 파일 경로와 Python 인터프리터 구분).

## 남은 인수 항목

- 서명 인증서·서명/배포 정책, 기관 백신·폐쇄망 반입 승인
- 실제 실험실 Windows 버전, 100/150/200% DPI, 다중 모니터
- 실제 알림 표시·절전 복귀·로그아웃·재시작과 알림 실행기 종료 UX
- CTSPro에서 정확한 파일 해시의 조건 대조와 별도 장비 실행 승인
