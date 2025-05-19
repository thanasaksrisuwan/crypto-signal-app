@echo off
REM crypto-symbol-manager.bat - Script for managing crypto symbols via command line

setlocal EnableDelayedExpansion

set SCRIPT_DIR=%~dp0
set APP_DIR=%SCRIPT_DIR%app
set API_URL=http://localhost:8000/api/symbols

REM Check if command argument is 'check' to check service status
if /i "%~1"=="check" goto :check_services

REM Check if Python is available
where python >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo Python not found. Please install Python to use this script.
    exit /b 1
)

REM Check if requests module is installed
python -c "import requests" >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo Installing requests module...
    pip install requests
)

REM Check if services are running before proceeding
call :check_services quiet
if %ERRORLEVEL% NEQ 0 (
    echo Backend API is not running. Please start it using start-crypto-app.bat or start-backend.bat
    echo Do you want to continue anyway? (Y/N)
    set /p CONTINUE=
    if /i not "!CONTINUE!"=="Y" exit /b 1
)

REM Parse command line arguments
set ACTION=
set SYMBOL=
set LIST_ONLY=0

if "%~1"=="" goto :show_help
if /i "%~1"=="add" (
    set ACTION=add
    set SYMBOL=%~2
) else if /i "%~1"=="remove" (
    set ACTION=remove
    set SYMBOL=%~2
) else if /i "%~1"=="list" (
    set LIST_ONLY=1
) else if /i "%~1"=="help" (
    goto :show_help
) else (
    echo Unknown action: %~1
    goto :show_help
)

REM Generate Python script for symbol management
set TMP_SCRIPT=%TEMP%\sym_manager_%RANDOM%.py
(
echo import requests
echo import sys
echo import json
echo.
echo API_URL = "%API_URL%"
echo.
echo def list_symbols^(^):
echo     try:
echo         response = requests.get^(f"^^{API_URL}"^)
echo         data = response.json^(^)
echo         if data.get^('success'^):
echo             print^("Available Symbols:"^)
echo             for i, symbol in enumerate^(data.get^('symbols', []^)^):
echo                 print^(f"  ^^{i+1^}. ^^{symbol^}"^)
echo             print^(f"\nTotal: ^^{len^(data.get^('symbols', []^)^)^} symbols"^)
echo         else:
echo             print^(f"Error: ^^{data.get^('message', 'Unknown error'^)^}"^)
echo     except Exception as e:
echo         print^(f"Error connecting to API: ^^{e^}"^)
echo.
echo def add_symbol^(symbol^):
echo     try:
echo         response = requests.post^(f"^^{API_URL}/add", json=^{"symbol": symbol^}^)
echo         data = response.json^(^)
echo         if data.get^('success'^):
echo             print^(f"Symbol '^^{symbol^}' added successfully"^)
echo             print^(f"Current symbols: ^^{', '.join^(data.get^('symbols', []^)^)^}"^)
echo         else:
echo             print^(f"Error: ^^{data.get^('message', 'Unknown error'^)^}"^)
echo     except Exception as e:
echo         print^(f"Error connecting to API: ^^{e^}"^)
echo.
echo def remove_symbol^(symbol^):
echo     try:
echo         response = requests.post^(f"^^{API_URL}/remove", json=^{"symbol": symbol^}^)
echo         data = response.json^(^)
echo         if data.get^('success'^):
echo             print^(f"Symbol '^^{symbol^}' removed successfully"^)
echo             print^(f"Current symbols: ^^{', '.join^(data.get^('symbols', []^)^)^}"^)
echo         else:
echo             print^(f"Error: ^^{data.get^('message', 'Unknown error'^)^}"^)
echo     except Exception as e:
echo         print^(f"Error connecting to API: ^^{e^}"^)
echo.
echo if __name__ == "__main__":
if !LIST_ONLY! EQU 1 (
    echo     list_symbols^(^)
) else if "!ACTION!"=="add" (
    echo     add_symbol^("%SYMBOL%"^)
) else if "!ACTION!"=="remove" (
    echo     remove_symbol^("%SYMBOL%"^)
)
) > "%TMP_SCRIPT%"

REM Execute the Python script
python "%TMP_SCRIPT%"

REM Clean up
del "%TMP_SCRIPT%" >nul 2>nul

goto :eof

:check_services
REM Check if services are running
echo ====== ตรวจสอบสถานะบริการ ======

REM Check if Redis is running
tasklist /fi "imagename eq redis-server.exe" | find "redis-server.exe" > nul
if %ERRORLEVEL% EQU 0 (
    if not "%~1"=="quiet" echo [✓] Redis Server: กำลังทำงาน
) else (
    if not "%~1"=="quiet" echo [✗] Redis Server: ไม่ได้ทำงาน
)

REM Check if Backend API is running by checking port 8000
netstat -ano | find ":8000" | find "LISTENING" > nul
if %ERRORLEVEL% EQU 0 (
    if not "%~1"=="quiet" echo [✓] Backend API: กำลังทำงาน (พอร์ต 8000)
    
    REM Try to access the API to verify it's working correctly
    echo import requests > "%TEMP%\check_api.py"
    echo try: >> "%TEMP%\check_api.py"
    echo     response = requests.get("http://localhost:8000/") >> "%TEMP%\check_api.py"
    echo     if response.status_code == 200: >> "%TEMP%\check_api.py"
    echo         print("API responding normally") >> "%TEMP%\check_api.py"
    echo     else: >> "%TEMP%\check_api.py"
    echo         print(f"API responded with status code: {response.status_code}") >> "%TEMP%\check_api.py"
    echo except Exception as e: >> "%TEMP%\check_api.py"
    echo     print(f"Error: {e}") >> "%TEMP%\check_api.py"
    echo     exit(1) >> "%TEMP%\check_api.py"
    
    python "%TEMP%\check_api.py" > nul 2>&1
    if %ERRORLEVEL% EQU 0 (
        if not "%~1"=="quiet" echo [✓] Backend API: ทำงานและตอบสนองปกติ
        del "%TEMP%\check_api.py" > nul 2>&1
        exit /b 0
    ) else (
        if not "%~1"=="quiet" echo [!] Backend API: พอร์ตทำงานแต่ API ไม่ตอบสนอง
        del "%TEMP%\check_api.py" > nul 2>&1
    )
) else (
    if not "%~1"=="quiet" echo [✗] Backend API: ไม่ได้ทำงาน
    exit /b 1
)

REM Check if Frontend is running (port 3000)
netstat -ano | find ":3000" | find "LISTENING" > nul
if %ERRORLEVEL% EQU 0 (
    if not "%~1"=="quiet" echo [✓] Frontend: กำลังทำงาน (พอร์ต 3000)
) else (
    if not "%~1"=="quiet" echo [✗] Frontend: ไม่ได้ทำงาน
)

if "%~1"=="quiet" exit /b 0
echo.
echo ใช้คำสั่ง "start-crypto-app.bat" เพื่อเริ่มต้นทุกบริการพร้อมกัน
echo หรือใช้คำสั่ง "start-redis.bat", "start-backend.bat" และ "start-frontend.bat" เพื่อเริ่มต้นแต่ละบริการแยกกัน
echo.
exit /b 0

:show_help
echo.
echo Crypto Symbol Manager - Command line tool for managing crypto symbols
echo.
echo Usage:
echo   %~n0 list                - List all available symbols
echo   %~n0 add [symbol]        - Add a new symbol (e.g. BTCUSDT)
echo   %~n0 remove [symbol]     - Remove an existing symbol
echo   %~n0 check               - Check if services are running
echo   %~n0 help                - Show this help message
echo.
echo Examples:
echo   %~n0 list
echo   %~n0 add DOGEUSDT
echo   %~n0 remove ETHUSDT
echo   %~n0 check
echo.
echo Note: The backend API must be running for this tool to work.
echo.
goto :eof
