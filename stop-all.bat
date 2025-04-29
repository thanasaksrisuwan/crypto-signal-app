@echo off
REM ======================================================================
REM Crypto Signal App - Stop All Components
REM หยุดการทำงานของระบบทั้งหมด (Redis, Backend, Frontend)
REM ======================================================================

setlocal enabledelayedexpansion

echo.
echo ====== หยุดการทำงานระบบทั้งหมด ======
echo.

REM หยุดการทำงานของ Frontend (Node.js บนพอร์ต 3000)
echo กำลังหยุดการทำงานของ Frontend...
for /f "tokens=5" %%a in ('netstat -ano ^| find ":3000" ^| find "LISTENING"') do (
    echo ยกเลิกกระบวนการ %%a
    taskkill /f /pid %%a > nul 2>&1
    if %errorlevel% equ 0 (
        echo หยุด Frontend สำเร็จ
    ) else (
        echo ไม่พบการทำงานของ Frontend หรือไม่สามารถหยุดได้
    )
)

REM หยุดการทำงานของ Backend API (Python/uvicorn บนพอร์ต 8000)
echo.
echo กำลังหยุดการทำงานของ Backend API...
for /f "tokens=5" %%a in ('netstat -ano ^| find ":8000" ^| find "LISTENING"') do (
    echo ยกเลิกกระบวนการ %%a
    taskkill /f /pid %%a > nul 2>&1
    if %errorlevel% equ 0 (
        echo หยุด Backend API สำเร็จ
    ) else (
        echo ไม่พบการทำงานของ Backend API หรือไม่สามารถหยุดได้
    )
)

REM หยุดการทำงานของ Redis Server
echo.
echo กำลังหยุดการทำงานของ Redis Server...
taskkill /f /im redis-server.exe > nul 2>&1
if %errorlevel% equ 0 (
    echo หยุด Redis Server สำเร็จ
) else (
    echo ไม่พบการทำงานของ Redis Server
)

echo.
echo ====== หยุดการทำงานระบบทั้งหมดเสร็จสมบูรณ์ ======
echo.

endlocal