@echo off
setlocal

if not exist venv\Scripts\python.exe (
  echo [ERROR] Virtual environment not found at venv\Scripts\python.exe
  echo Create it first with: py -3.11 -m venv venv
  exit /b 1
)

call venv\Scripts\activate
python run_api.py