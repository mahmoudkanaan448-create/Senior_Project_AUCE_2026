@echo off

REM Desktop launcher – AI Network Analyzer (NDR 2.0)

REM Stops stale API/Dashboard, clears cache, verifies DB, then starts fresh.

cd /d "%~dp0"



set PY=C:\aindr_venv\Scripts\python.exe

set STREAMLIT=C:\aindr_venv\Scripts\streamlit.exe

set API_PORT=8000

set DASH_PORT=8501



if not exist "%PY%" (

  echo ERROR: Python venv not found at C:\aindr_venv

  echo Run: python -m venv C:\aindr_venv

  echo Then: C:\aindr_venv\Scripts\pip install -r requirements.txt

  pause

  exit /b 1

)



echo.

echo [1/5] Stopping old API / Dashboard on ports %API_PORT% and %DASH_PORT%...

for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":%DASH_PORT% " ^| findstr LISTENING') do taskkill /F /PID %%a >nul 2>&1

for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":%API_PORT% " ^| findstr LISTENING') do taskkill /F /PID %%a >nul 2>&1

taskkill /F /FI "WINDOWTITLE eq AI-NDR-API*" >nul 2>&1

taskkill /F /FI "WINDOWTITLE eq AI-NDR-Dashboard*" >nul 2>&1

timeout /t 2 /nobreak >nul



echo [2/5] Clearing Python cache...

for /d /r %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d" 2>nul



echo [3/5] Verifying database / ORM...

"%PY%" scripts\verify_orm.py

if errorlevel 1 (

  echo.

  echo ERROR: Database check failed. See message above.

  pause

  exit /b 1

)



echo [4/5] Starting API (port %API_PORT%)...

start "AI-NDR-API" /D "%~dp0" "%PY%" main.py

timeout /t 4 /nobreak >nul



echo [5/5] Starting Dashboard (port %DASH_PORT%)...

start "AI-NDR-Dashboard" /D "%~dp0" "%STREAMLIT%" run dashboard\home.py --server.port %DASH_PORT% --server.headless true --browser.gatherUsageStats false

timeout /t 5 /nobreak >nul



start "" "http://localhost:%DASH_PORT%"



echo.

echo ========================================

echo   AI Network Analyzer is running

echo   Dashboard: http://localhost:%DASH_PORT%

echo   API:       http://localhost:%API_PORT%

echo   Login:     admin / admin123

echo ========================================

echo.

echo Keep the API and Dashboard windows open.

echo To restart: close those windows, then run this file again.

echo.

pause


