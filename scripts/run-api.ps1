Set-Location (Join-Path $PSScriptRoot "..\apps\api")
& "D:\AI-Tracing\venv\Scripts\python.exe" -m uvicorn app.main:app --reload --port 8000
