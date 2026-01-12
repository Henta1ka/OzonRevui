@echo off
REM Quick Start Script for Ozon Review Service (Windows)

echo.
echo 🚀 Ozon Review Service - Quick Start
echo =====================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python not found. Please install Python 3.9+
    exit /b 1
)

echo ✅ Python found: 
python --version
echo.

REM Create virtual environment
if not exist "venv" (
    echo 📦 Creating virtual environment...
    python -m venv venv
    echo ✅ Virtual environment created
) else (
    echo ✅ Virtual environment already exists
)

echo.

REM Activate virtual environment
echo 🔧 Activating virtual environment...
call venv\Scripts\activate.bat
echo ✅ Virtual environment activated
echo.

REM Install dependencies
echo 📚 Installing dependencies...
pip install -q -r requirements.txt
echo ✅ Dependencies installed
echo.

REM Create .env if doesn't exist
if not exist ".env" (
    echo ⚙️ Creating .env file from template...
    copy .env.example .env
    echo ⚠️  Please edit .env and add your API keys!
    echo.
    type .env
) else (
    echo ✅ .env file already exists
)

echo.
echo 🎯 Setup complete!
echo.
echo Next steps:
echo 1. Edit .env and add your API credentials:
echo    - OZON_CLIENT_ID
echo    - OZON_API_KEY
echo    - OPENAI_API_KEY
echo.
echo 2. Run the server:
echo    python main.py
echo.
echo 3. Open in browser:
echo    http://localhost:8000
echo.
echo 4. API docs:
echo    http://localhost:8000/docs
echo.
pause
