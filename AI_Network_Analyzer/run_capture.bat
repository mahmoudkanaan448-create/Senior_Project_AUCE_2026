@echo off
cd /d "%~dp0"
set PY=C:\aindr_venv\Scripts\python.exe
if not exist "%PY%" set PY=python
echo Starting 24/7 capture daemon...
echo Close this window to stop capture.
"%PY%" -m monitoring.capture_daemon --iface auto --detect
pause
