@echo off
REM Production / server launcher with auto-restart supervisor
cd /d "%~dp0"

set PY=C:\aindr_venv\Scripts\python.exe
if not exist "%PY%" set PY=python

set AINDR_PYTHON=%PY%
if exist "C:\aindr_venv\Scripts\streamlit.exe" (
  set AINDR_STREAMLIT=C:\aindr_venv\Scripts\streamlit.exe
) else (
  set AINDR_STREAMLIT=streamlit
)

set AINDR_API_PORT=8000
set AINDR_DASH_PORT=8501
set AINDR_CHECK_SECONDS=15

echo Clearing stale Python cache...
for /d /r %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d" 2>nul

echo Stopping old dashboard/API on ports %AINDR_DASH_PORT% / %AINDR_API_PORT%...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":%AINDR_DASH_PORT% " ^| findstr LISTENING') do taskkill /F /PID %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":%AINDR_API_PORT% " ^| findstr LISTENING') do taskkill /F /PID %%a >nul 2>&1

echo ========================================
echo  AI-NDR Server Mode (auto-recovery)
echo  API:        http://0.0.0.0:%AINDR_API_PORT%
echo  Dashboard:  http://0.0.0.0:%AINDR_DASH_PORT%
echo  Health:     http://127.0.0.1:%AINDR_API_PORT%/api/v1/health
echo  Logs:       logs\supervisor.log
echo ========================================
echo.
echo Supervisor keeps API + Dashboard alive.
echo Press Ctrl+C to stop.
echo.

"%PY%" -m ops.supervisor
pause
