@echo off
echo 🤖 AI Excuse Generator - Starting Up...
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python is not installed or not in PATH
    echo Please install Python 3.8+ from https://python.org
    pause
    exit /b 1
)

REM Check if virtual environment exists
if not exist "venv" (
    echo 📦 Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo ❌ Failed to create virtual environment
        pause
        exit /b 1
    )
)

REM Activate virtual environment
echo 🔧 Activating virtual environment...
call venv\Scripts\activate.bat

REM Install/upgrade dependencies
echo 📦 Installing dependencies...
pip install -r requirements.txt

REM Check if .env file exists
if not exist ".env" (
    echo ⚠️  .env file not found
    echo 📝 Creating .env file from template...
    copy env_example.txt .env
    echo.
    echo ⚠️  IMPORTANT: Please edit the .env file and add your OpenAI API key
    echo    You can get one from: https://platform.openai.com/
    echo.
    pause
)

REM Start the application
echo 🚀 Starting AI Excuse Generator...
echo.
echo 📱 The application will open at: http://localhost:5000
echo 🛑 Press Ctrl+C to stop the application
echo.
python app.py

pause
