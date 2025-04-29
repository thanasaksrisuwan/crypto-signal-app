@echo off
REM ======================================================================
REM Crypto Signal App Helper Script
REM เครื่องมือช่วยเหลือสำหรับแอพ Crypto Signal
REM ======================================================================

setlocal enabledelayedexpansion

echo.
echo ====== Crypto Signal App ======
echo.

REM ตั้งค่าตัวแปรพื้นฐาน
set "SCRIPT_DIR=%~dp0"
set "APP_DIR=%SCRIPT_DIR%app"
set "FRONTEND_DIR=%SCRIPT_DIR%frontend"
set "REDIS_DIR=%SCRIPT_DIR%redis"
set "VIRTUAL_ENV=%SCRIPT_DIR%venv"

REM ตรวจสอบว่ามีการส่งคำสั่งหรือไม่
if "%1"=="" goto :show_menu

REM จัดการคำสั่งต่างๆ
if "%1"=="help" goto :show_help
if "%1"=="setup" goto :setup
if "%1"=="start" goto :start_all
if "%1"=="stop" goto :stop_all
if "%1"=="redis" goto :start_redis
if "%1"=="backend" goto :start_backend
if "%1"=="frontend" goto :start_frontend
if "%1"=="test" goto :run_tests
if "%1"=="update" goto :update_deps

echo คำสั่ง %1 ไม่ถูกต้อง โปรดลองใหม่
goto :show_menu

:show_menu
echo เลือกคำสั่งที่ต้องการ:
echo.
echo   1. setup    - ติดตั้งสภาพแวดล้อมและติดตั้ง dependencies
echo   2. start    - เริ่มต้นระบบทั้งหมด (Redis, Backend, Frontend)
echo   3. stop     - หยุดระบบทั้งหมด
echo   4. redis    - เริ่มต้น Redis Server เท่านั้น
echo   5. backend  - เริ่มต้น Backend API เท่านั้น
echo   6. frontend - เริ่มต้น Frontend เท่านั้น
echo   7. test     - รันการทดสอบ
echo   8. update   - อัปเดต dependencies
echo   9. help     - แสดงวิธีใช้งาน
echo.
echo เรียกใช้โดยใช้คำสั่ง: %~n0 [คำสั่ง]
echo.

set /p choice="เลือกตัวเลข (1-9): "

if "%choice%"=="1" goto :setup
if "%choice%"=="2" goto :start_all
if "%choice%"=="3" goto :stop_all
if "%choice%"=="4" goto :start_redis
if "%choice%"=="5" goto :start_backend
if "%choice%"=="6" goto :start_frontend
if "%choice%"=="7" goto :run_tests
if "%choice%"=="8" goto :update_deps
if "%choice%"=="9" goto :show_help

echo ตัวเลือกไม่ถูกต้อง โปรดลองใหม่
goto :eof

:show_help
echo.
echo ====== Crypto Signal App - วิธีการใช้งาน ======
echo.
echo คำสั่งต่างๆ:
echo   %~n0 setup    - ติดตั้งสภาพแวดล้อมและติดตั้ง dependencies
echo   %~n0 start    - เริ่มต้นระบบทั้งหมด (Redis, Backend, Frontend)
echo   %~n0 stop     - หยุดระบบทั้งหมด
echo   %~n0 redis    - เริ่มต้น Redis Server เท่านั้น
echo   %~n0 backend  - เริ่มต้น Backend API เท่านั้น
echo   %~n0 frontend - เริ่มต้น Frontend เท่านั้น
echo   %~n0 test     - รันการทดสอบ
echo   %~n0 update   - อัปเดต dependencies
echo.
goto :eof

:setup
echo.
echo ====== ติดตั้งสภาพแวดล้อมและติดตั้ง dependencies ======
echo.

REM ตรวจสอบว่ามี Python ติดตั้งหรือไม่
python --version > nul 2>&1
if %errorlevel% neq 0 (
    echo ไม่พบการติดตั้ง Python โปรดติดตั้ง Python 3.8 หรือใหม่กว่า
    goto :eof
)

REM ตรวจสอบว่ามี Node.js ติดตั้งหรือไม่
node --version > nul 2>&1
if %errorlevel% neq 0 (
    echo ไม่พบการติดตั้ง Node.js โปรดติดตั้ง Node.js สำหรับ Frontend
    goto :eof
)

REM สร้าง Virtual Environment ถ้ายังไม่มี
if not exist "%VIRTUAL_ENV%" (
    echo สร้าง Virtual Environment...
    python -m venv "%VIRTUAL_ENV%"
)

REM ติดตั้ง Python dependencies
echo ติดตั้ง Python dependencies...
call "%VIRTUAL_ENV%\Scripts\activate.bat"
pip install -r "%SCRIPT_DIR%requirements.txt"

REM ติดตั้ง Node.js dependencies สำหรับ Frontend
if exist "%FRONTEND_DIR%\package.json" (
    echo ติดตั้ง Node.js dependencies สำหรับ Frontend...
    cd "%FRONTEND_DIR%"
    npm install
)

REM ตรวจสอบว่ามีไฟล์ .env หรือไม่ และสร้างถ้ายังไม่มี
if not exist "%SCRIPT_DIR%.env" (
    echo สร้างไฟล์ .env ตัวอย่าง...
    echo # Crypto Signal App Configuration > "%SCRIPT_DIR%.env"
    echo REDIS_HOST=localhost >> "%SCRIPT_DIR%.env"
    echo REDIS_PORT=6379 >> "%SCRIPT_DIR%.env"
    echo REDIS_PASSWORD= >> "%SCRIPT_DIR%.env"
    echo # InfluxDB Configuration >> "%SCRIPT_DIR%.env"
    echo INFLUXDB_URL=http://localhost:8086 >> "%SCRIPT_DIR%.env"
    echo INFLUXDB_TOKEN=your_token_here >> "%SCRIPT_DIR%.env"
    echo INFLUXDB_ORG=your_org_here >> "%SCRIPT_DIR%.env"
    echo INFLUXDB_BUCKET=crypto_signals >> "%SCRIPT_DIR%.env"
    echo # Binance API Configuration >> "%SCRIPT_DIR%.env"
    echo BINANCE_API_KEY= >> "%SCRIPT_DIR%.env"
    echo BINANCE_API_SECRET= >> "%SCRIPT_DIR%.env"
    echo. >> "%SCRIPT_DIR%.env"
    echo โปรดแก้ไขไฟล์ .env และกำหนดค่าที่เหมาะสม
)

echo.
echo การติดตั้งเสร็จสมบูรณ์!
echo.
goto :eof

:start_all
echo.
echo ====== เริ่มต้นระบบทั้งหมด ======
echo.

REM เปิด CMD ใหม่สำหรับ Redis Server
start "Redis Server" cmd /c "cd "%REDIS_DIR%" && redis-server.exe redis.windows.conf"
echo เริ่มต้น Redis Server...
timeout /t 3 > nul

REM เปิด CMD ใหม่สำหรับ Backend API
start "Backend API" cmd /c "call "%VIRTUAL_ENV%\Scripts\activate.bat" && cd "%APP_DIR%" && python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload"
echo เริ่มต้น Backend API...
timeout /t 3 > nul

REM เปิด CMD ใหม่สำหรับ Frontend
start "Frontend" cmd /c "cd "%FRONTEND_DIR%" && npm start"
echo เริ่มต้น Frontend...

echo.
echo ระบบทั้งหมดเริ่มต้นแล้ว!
echo.
goto :eof

:stop_all
echo.
echo ====== หยุดระบบทั้งหมด ======
echo.

REM หยุดการทำงานของ Redis Server
taskkill /f /im redis-server.exe > nul 2>&1
if %errorlevel% equ 0 (
    echo หยุด Redis Server สำเร็จ
) else (
    echo ไม่พบการทำงานของ Redis Server
)

REM หยุดการทำงานของ Backend API (uvicorn)
taskkill /f /im python.exe /fi "WINDOWTITLE eq Backend API*" > nul 2>&1
if %errorlevel% equ 0 (
    echo หยุด Backend API สำเร็จ
) else (
    echo ไม่พบการทำงานของ Backend API
)

REM หยุดการทำงานของ Frontend (Node.js)
taskkill /f /im node.exe /fi "WINDOWTITLE eq Frontend*" > nul 2>&1
if %errorlevel% equ 0 (
    echo หยุด Frontend สำเร็จ
) else (
    echo ไม่พบการทำงานของ Frontend
)

echo.
echo ระบบทั้งหมดถูกหยุดแล้ว!
echo.
goto :eof

:start_redis
echo.
echo ====== เริ่มต้น Redis Server ======
echo.
start "Redis Server" cmd /c "cd "%REDIS_DIR%" && redis-server.exe redis.windows.conf"
echo Redis Server เริ่มต้นแล้ว!
echo.
goto :eof

:start_backend
echo.
echo ====== เริ่มต้น Backend API ======
echo.
start "Backend API" cmd /c "call "%VIRTUAL_ENV%\Scripts\activate.bat" && cd "%APP_DIR%" && python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload"
echo Backend API เริ่มต้นแล้ว!
echo.
goto :eof

:start_frontend
echo.
echo ====== เริ่มต้น Frontend ======
echo.
if exist "%FRONTEND_DIR%\package.json" (
    REM สำหรับกรณีใช้ PowerShell ซึ่งมีปัญหากับการใช้ && ในคำสั่ง
    echo กำลังเริ่มต้น Frontend React application...
    pushd "%FRONTEND_DIR%"
    start "Frontend" cmd /k "npm start"
    popd
    echo Frontend เริ่มต้นแล้ว!
) else (
    echo ไม่พบไฟล์ package.json ในโฟลเดอร์ Frontend
)
echo.
goto :eof

:run_tests
echo.
echo ====== รันการทดสอบ ======
echo.
call "%VIRTUAL_ENV%\Scripts\activate.bat"
cd "%APP_DIR%"
python -m pytest -v
echo.
goto :eof

:update_deps
echo.
echo ====== อัปเดต dependencies ======
echo.

REM อัปเดต Python dependencies
echo อัปเดต Python dependencies...
call "%VIRTUAL_ENV%\Scripts\activate.bat"
pip install --upgrade -r "%SCRIPT_DIR%requirements.txt"

REM อัปเดต Node.js dependencies สำหรับ Frontend
if exist "%FRONTEND_DIR%\package.json" (
    echo อัปเดต Node.js dependencies สำหรับ Frontend...
    cd "%FRONTEND_DIR%"
    npm update
)

echo.
echo อัปเดต dependencies เสร็จสมบูรณ์!
echo.
goto :eof

:eof
endlocal