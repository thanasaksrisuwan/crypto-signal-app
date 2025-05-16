@echo off
REM ======================================================================
REM Frontend Starter
REM This script starts the React frontend for the Crypto Signal App.
REM ======================================================================

setlocal enabledelayedexpansion

echo.
echo ====== Starting Frontend ======
echo.

REM Set base directories
set "SCRIPT_DIR=%~dp0"
set "FRONTEND_DIR=%SCRIPT_DIR%frontend"
set "LOG_DIR=%SCRIPT_DIR%logs"

REM Check if frontend directory exists
if not exist "%FRONTEND_DIR%" (
    echo Frontend directory not found at %FRONTEND_DIR%.
    exit /b 1
)

REM Ensure logs directory exists
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

REM Check if Frontend is already running
netstat -ano | find ":3000" | find "LISTENING" > nul
if %errorlevel% equ 0 (
    echo Frontend is already running on port 3000.
    exit /b 0
)

REM Check if node_modules exists, if not run npm install
if not exist "%FRONTEND_DIR%\node_modules" (
    echo Installing dependencies...
    cd "%FRONTEND_DIR%" && npm install
    if %errorlevel% neq 0 (
        echo Failed to install dependencies.
        exit /b 1
    )
)

REM Start Frontend
start "Frontend" cmd /c "cd "%FRONTEND_DIR%" && npm start > "%LOG_DIR%\frontend.log" 2>&1"
if %errorlevel% neq 0 (
    echo Failed to start Frontend.
    exit /b 1
)

echo Frontend started successfully at http://localhost:3000
echo.

endlocal