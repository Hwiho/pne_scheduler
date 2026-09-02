@echo off
chcp 65001 > nul
echo Battery Scheduler 시작 중...

:: Flask 설치 확인
python -c "import flask" 2>nul
if errorlevel 1 (
    echo Flask 설치 중...
    pip install flask
)

python app.py
pause
