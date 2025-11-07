@echo off
REM Batch script to collect static files for Django

echo ==================================
echo Collecting Static Files
echo ==================================

REM Set the Python executable path (adjust if needed)
set PYTHON_PATH=C:\Python313\python.exe

REM Set Django settings module
set DJANGO_SETTINGS_MODULE=service_booking.settings_production

REM Navigate to project directory
cd /d "%~dp0\.."

REM Collect static files
echo Running collectstatic...
%PYTHON_PATH% manage.py collectstatic --noinput

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ==================================
    echo Static files collected successfully!
    echo ==================================
) else (
    echo.
    echo ==================================
    echo ERROR: Failed to collect static files
    echo ==================================
    exit /b 1
)

pause
