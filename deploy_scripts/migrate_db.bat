@echo off
REM Batch script to run Django migrations

echo ==================================
echo Running Database Migrations
echo ==================================

REM Set the Python executable path (adjust if needed)
set PYTHON_PATH=C:\Python313\python.exe

REM Set Django settings module
set DJANGO_SETTINGS_MODULE=service_booking.settings_production

REM Navigate to project directory
cd /d "%~dp0\.."

REM Check for pending migrations
echo Checking for pending migrations...
%PYTHON_PATH% manage.py showmigrations

echo.
echo ==================================
echo Running migrations...
echo ==================================
%PYTHON_PATH% manage.py migrate

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ==================================
    echo Migrations completed successfully!
    echo ==================================
) else (
    echo.
    echo ==================================
    echo ERROR: Migrations failed
    echo ==================================
    exit /b 1
)

pause
