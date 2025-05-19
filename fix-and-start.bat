@echo off
REM filepath: c:\Users\Nack\Documents\crypto-signal-app\fix-and-start.bat
REM ===================================================================
REM แก้ไขและเริ่มต้นบริการ Crypto Signal App
REM ===================================================================
setlocal EnableDelayedExpansion

echo ======================================================
echo       CRYPTO SIGNAL APP - FIX AND START UTILITY
echo ======================================================
echo.

REM ตั้งค่าตำแหน่งของไดเรกทอรี่
set "APP_DIR=%~dp0"
cd %APP_DIR%
set "BACKEND_DIR=%APP_DIR%app"
set "FRONTEND_DIR=%APP_DIR%frontend"
set "REDIS_DIR=%APP_DIR%redis"

echo [INFO] กำลังตรวจสอบสภาพแวดล้อม...

REM ตรวจสอบ Python
where python >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] ไม่พบการติดตั้ง Python กรุณาติดตั้ง Python ก่อนใช้งาน
    goto :error_exit
) else (
    python --version
    echo [✓] พบการติดตั้ง Python แล้ว
)

REM ตรวจสอบ Node.js
where node >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] ไม่พบการติดตั้ง Node.js กรุณาติดตั้ง Node.js ก่อนใช้งาน
    goto :error_exit
) else (
    node --version
    echo [✓] พบการติดตั้ง Node.js แล้ว
)

REM ตรวจสอบ Redis
if not exist "%REDIS_DIR%\redis-server.exe" (
    echo [ERROR] ไม่พบไฟล์ redis-server.exe ใน %REDIS_DIR%
    goto :error_exit
) else (
    echo [✓] พบไฟล์ Redis Server แล้ว
)

echo.
echo [INFO] กำลังเริ่มหยุดบริการที่อาจทำงานค้างอยู่...

REM หยุด Redis Server (ถ้ากำลังทำงานอยู่)
tasklist /fi "imagename eq redis-server.exe" 2>nul | find "redis-server.exe" > nul
if %ERRORLEVEL% EQU 0 (
    echo [INFO] กำลังหยุด Redis Server...
    taskkill /f /im redis-server.exe > nul 2>&1
    echo [✓] หยุด Redis Server แล้ว
)

REM หยุด Backend (ถ้ากำลังทำงานอยู่)
netstat -ano 2>nul | find ":8000" | find "LISTENING" > nul
if %ERRORLEVEL% EQU 0 (
    for /f "tokens=5" %%a in ('netstat -ano ^| find ":8000" ^| find "LISTENING"') do (
        echo [INFO] กำลังหยุด Backend API (PID: %%a)...
        taskkill /f /pid %%a > nul 2>&1
        echo [✓] หยุด Backend API แล้ว
    )
)

REM หยุด Frontend (ถ้ากำลังทำงานอยู่)
netstat -ano 2>nul | find ":3000" | find "LISTENING" > nul
if %ERRORLEVEL% EQU 0 (
    for /f "tokens=5" %%a in ('netstat -ano ^| find ":3000" ^| find "LISTENING"') do (
        echo [INFO] กำลังหยุด Frontend (PID: %%a)...
        taskkill /f /pid %%a > nul 2>&1
        echo [✓] หยุด Frontend แล้ว
    )
)

REM รอให้กระบวนการต่างๆ หยุดทำงานสมบูรณ์
timeout /t 3 > nul

echo.
echo [INFO] กำลังเริ่มต้นบริการใหม่...

REM เริ่มต้น Redis Server
echo [INFO] กำลังเริ่มต้น Redis Server...
start "Redis Server" cmd /c "cd %REDIS_DIR% && redis-server.exe redis.windows.conf"
echo [✓] เริ่มต้น Redis Server แล้ว
ping -n 3 127.0.0.1 > nul

REM เริ่มต้น Backend Server
echo [INFO] กำลังเริ่มต้น Backend Server...
start "Crypto Signal Backend" cmd /c "cd %BACKEND_DIR% && python main.py"
echo [✓] เริ่มต้น Backend API แล้ว
ping -n 5 127.0.0.1 > nul

REM เริ่มต้น Frontend Server
echo [INFO] กำลังเริ่มต้น Frontend Server...
start "Crypto Signal Frontend" cmd /c "cd %FRONTEND_DIR% && npm start"
echo [✓] เริ่มต้น Frontend แล้ว

echo.
echo [INFO] กำลังเปิดแอปพลิเคชัน... รอสักครู่ (15 วินาที)
echo [INFO] ระบบกำลังทำงาน...
timeout /t 15 > nul

echo.
echo ======================================================
echo    CRYPTO SIGNAL APP กำลังทำงาน! เปิดแอปพลิเคชันใน Browser แล้ว
echo ======================================================
start "" http://localhost:3000

echo.
echo [INFO] กำลังตรวจสอบสถานะบริการ...
echo.

call "%APP_DIR%\test-app-status.bat"

exit /b 0

:error_exit
echo.
echo [ERROR] การเริ่มต้นแอปพลิเคชันล้มเหลว โปรดแก้ไขปัญหาที่แสดงด้านบนแล้วลองอีกครั้ง
pause
exit /b 1
