# Cursor Cloud 저장소 설정 (WSL)

Cursor Cloud(`origin.cursor.com`)는 **WSL/Linux/macOS**에서만 `origin` CLI로 관리할 수 있습니다.  
Windows PowerShell 단독으로는 지원되지 않습니다.

## 사전 조건

- Windows 10/11 + WSL2
- `pne_scheduler` GitHub 저장소 클론 또는 로컬 복사
- Cursor 계정 (팀 namespace 필요 시 [cursor.com/codebase](https://cursor.com/codebase)에서 설정)

## 1단계: WSL 설치 (최초 1회)

관리자 PowerShell:

```powershell
cd C:\Users\LGES\Cursor\pne_scheduler
.\scripts\setup_cursor_cloud.ps1
```

이 스크립트가 다음을 수행합니다.

1. WSL + Virtual Machine Platform 기능 활성화
2. WSL 2.7+ 및 Ubuntu 설치
3. **재부팅 필요 시 안내**

재부팅 후:

```powershell
.\scripts\setup_cursor_cloud.ps1 -SkipWslInstall
```

## 2단계: origin CLI 로그인 (WSL)

재부팅 후 WSL에서 직접 실행할 수도 있습니다.

```bash
cd /mnt/c/Users/LGES/Cursor/pne_scheduler
bash scripts/setup_cursor_cloud.sh
```

처음 실행 시 브라우저가 열리며 Cursor 로그인이 필요합니다 (`origin auth login`).

## 3단계: 결과

성공 시:

| Remote | URL |
|--------|-----|
| `origin` | GitHub (`https://github.com/Hwiho/pne_scheduler.git`) |
| `cursor` | Cursor Cloud (`https://origin.cursor.com/...`) |

저장소 페이지: `https://cursor.com/codebase/<namespace>/pne_scheduler`

## 수동 명령 (참고)

```bash
# origin CLI 설치
curl -fsSL https://downloads.cursor.com/origin/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"

# 로그인
origin auth login

# 저장소 생성 + push
cd /mnt/c/Users/LGES/Cursor/pne_scheduler
origin repo create pne_scheduler
git remote add cursor <clone-url-from-create>
git push -u cursor master
```

## 문제 해결

| 증상 | 해결 |
|------|------|
| `wsl: command not found` / WSL 미설치 | `.\scripts\setup_cursor_cloud.ps1` 실행 후 재부팅 |
| `origin: command not found` | `curl ... install.sh \| sh` 후 `export PATH=$HOME/.local/bin:$PATH` |
| 인증 실패 | `origin auth login` 재실행 |
| namespace 없음 | 팀 관리자가 cursor.com/codebase에서 namespace 설정 |
| repo 이름 충돌 | `origin repo create pne-scheduler-lges` 등 다른 이름 사용 |

## GitHub vs Cursor Cloud

- **GitHub (`origin`)**: 공개/협업용, 이미 설정됨
- **Cursor Cloud (`cursor`)**: Cursor IDE 통합, 비공개 호스팅

두 remote를 동시에 유지합니다. GitHub에 push한 뒤 Cursor에도 동기화:

```bash
git push origin master
git push cursor master
```
