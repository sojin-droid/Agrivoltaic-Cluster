@echo off
cd /d "%~dp0"
python --version >nul 2>&1
if %errorlevel% neq 0 goto nopython
start /b python -m http.server 8002
timeout /t 2 /nobreak >nul
start "" "http://localhost:8002/index.html"
echo Server running on http://localhost:8002
echo Do not close this window.
pause >nul
exit

:nopython
echo Python not found. Opening file directly.
start index.html
pause
exit