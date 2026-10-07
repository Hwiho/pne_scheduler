param(
  [Parameter(Mandatory=$true)][string]$PythonwPath
)

$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $PythonwPath -PathType Leaf)) {
  throw "pythonw.exe 파일을 찾을 수 없습니다: $PythonwPath"
}
if ([IO.Path]::GetFileName($PythonwPath).ToLowerInvariant() -ne 'pythonw.exe') {
  throw '이 설치 스크립트에는 같은 Python 환경의 pythonw.exe를 지정하세요.'
}
$startup = [Environment]::GetFolderPath('Startup')
$commonStartup = [Environment]::GetFolderPath('CommonStartup')
if ([IO.Path]::GetFullPath($startup) -eq [IO.Path]::GetFullPath($commonStartup)) {
  throw '전체 사용자 시작프로그램에는 설치하지 않습니다. 현재 사용자 시작프로그램 경로를 확인하세요.'
}
$shortcutPath = Join-Path $startup 'PNE Storage Notifier.lnk'
if (Test-Path -LiteralPath $shortcutPath) {
  throw "시작프로그램 바로가기가 이미 있습니다. 덮어쓰지 않았습니다: $shortcutPath"
}
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = (Resolve-Path -LiteralPath $PythonwPath).Path
$shortcut.Arguments = '-m pne_scheduler.storage_companion'
$shortcut.WorkingDirectory = Split-Path -Parent $PythonwPath
$shortcut.Description = 'PNE Scheduler 고온저장 확인일 알림 (현재 사용자 세션)'
$shortcut.Save()
Write-Host "현재 Windows 사용자 시작프로그램에 등록했습니다: $shortcutPath"
Write-Host '다음 로그인부터 실행됩니다. 실제 Windows 알림 표시 여부는 시스템 알림 설정에서 확인하세요.'
