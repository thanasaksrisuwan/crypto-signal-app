@echo off
REM ======================================================================
REM Redis Server Starter
REM เริ่มต้น Redis Server สำหรับแอป Crypto Signal
REM ======================================================================

setlocal enabledelayedexpansion

echo.
echo ====== เริ่มต้น Redis Server ======
echo.

REM ตั้งค่าตัวแปรพื้นฐาน
set "SCRIPT_DIR=%~dp0"
set "REDIS_DIR=%SCRIPT_DIR%redis"

REM ตรวจสอบว่าโฟลเดอร์ Redis มีอยู่หรือไม่
if not exist "%REDIS_DIR%" (
    echo ไม่พบโฟลเดอร์ Redis ที่ %REDIS_DIR%
    echo โปรดตรวจสอบการติดตั้ง Redis
    goto :eof
)

REM ตรวจสอบว่ามีไฟล์ redis-server.exe หรือไม่
if not exist "%REDIS_DIR%\redis-server.exe" (
    echo ไม่พบไฟล์ redis-server.exe
    echo โปรดตรวจสอบการติดตั้ง Redis
    goto :eof
)

REM ตรวจสอบว่า Redis กำลังทำงานอยู่หรือไม่
tasklist /fi "imagename eq redis-server.exe" | find "redis-server.exe" > nul
if %errorlevel% equ 0 (
    echo Redis Server กำลังทำงานอยู่แล้ว
    goto :ask_restart
)

:start_redis
REM เริ่มต้น Redis Server
echo เริ่มต้น Redis Server...
start "Redis Server" /min cmd /c "cd "%REDIS_DIR%" && redis-server.exe redis.windows.conf"

echo Redis Server เริ่มต้นแล้ว!
echo ทำงานในพื้นหลัง (minimized window)
echo.
goto :eof

:ask_restart
echo.
set /p restart="Redis กำลังทำงานอยู่แล้ว คุณต้องการรีสตาร์ทหรือไม่? (Y/N): "
if /i "%restart%"=="Y" (
    echo กำลังรีสตาร์ท Redis Server...
    taskkill /f /im redis-server.exe > nul 2>&1
    timeout /t 2 > nul
    goto :start_redis
) else (
    echo ไม่มีการเปลี่ยนแปลง Redis Server ยังคงทำงานต่อไป
)

:eof
endlocal