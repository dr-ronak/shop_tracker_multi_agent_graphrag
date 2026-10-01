@echo off
echo === Shop Tracker GraphRAG - setup ===
python --version >nul 2>&1 || (echo Python not found. Install Python 3.10+ first. & pause & exit /b 1)
if not exist venv python -m venv venv
call venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
if not exist .env copy .env.example .env
echo.
echo Setup done. Edit .env and add your SERPAPI_API_KEY, then run run.bat
pause
