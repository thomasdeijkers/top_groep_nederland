@echo off
cd /d "%~dp0.."
".venv\Scripts\python.exe" -m uvicorn apps.api.main:app --host 127.0.0.1 --port 8000 >> "runtime\logs\staging.out.log" 2>> "runtime\logs\staging.err.log"
