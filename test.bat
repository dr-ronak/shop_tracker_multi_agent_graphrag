@echo off
cd /d "%~dp0"
call venv\Scripts\activate.bat
pip install -r requirements-dev.txt -q
pytest -v
pause
