@echo off
REM ================================================================
REM One-Click Crypto Signal App Launcher - แก้ไขเวอร์ชัน
REM ================================================================
setlocal EnableDelayedExpansion

REM ตรวจสอบพารามิเตอร์คำสั่ง
if /i "%~1"=="status" (
    echo ======================================================
    echo         CRYPTO SIGNAL APP - SERVICE STATUS
    echo ======================================================
    echo.
    call :check_services
    goto :eof
)

if /i "%~1"=="stop" (
    echo ======================================================
    echo         CRYPTO SIGNAL APP - STOPPING SERVICES
    echo ======================================================
    echo.
    call :stop_all_services
    goto :eof
)

if /i "%~1"=="help" (
    echo ======================================================
    echo         CRYPTO SIGNAL APP - HELP
    echo ======================================================
    echo.
    echo การใช้งาน: %~n0 [คำสั่ง]
    echo.
    echo คำสั่งที่รองรับ:
    echo   (ไม่ระบุ)  - เริ่มต้นบริการทั้งหมด (ถ้ายังไม่ได้เริ่มต้น)
    echo   status    - แสดงสถานะของบริการทั้งหมด
    echo   stop      - หยุดการทำงานของบริการทั้งหมด
    echo   help      - แสดงคำแนะนำการใช้งาน
    echo.
    goto :eof
)

echo ======================================================
echo         CRYPTO SIGNAL APP - ONE CLICK LAUNCHER
echo ======================================================
echo.

REM ตั้งค่าตำแหน่งของไดเรกทอรี่
set "APP_DIR=%~dp0"
cd %APP_DIR%
set "BACKEND_DIR=%APP_DIR%app"
set "FRONTEND_DIR=%APP_DIR%frontend"
set "REDIS_DIR=%APP_DIR%redis"

REM ตรวจสอบว่าบริการต่างๆ กำลังทำงานอยู่แล้วหรือไม่
echo [INFO] ตรวจสอบบริการที่กำลังทำงาน...
set REDIS_RUNNING=0
set BACKEND_RUNNING=0
set FRONTEND_RUNNING=0

REM ตรวจสอบ Redis
tasklist /fi "imagename eq redis-server.exe" | find "redis-server.exe" > nul
if %ERRORLEVEL% EQU 0 (
    echo [STATUS] Redis Server: กำลังทำงานอยู่แล้ว
    set REDIS_RUNNING=1
)

REM ตรวจสอบ Backend API (port 8000)
netstat -ano | find ":8000" | find "LISTENING" > nul
if %ERRORLEVEL% EQU 0 (
    echo [STATUS] Backend API: กำลังทำงานอยู่แล้ว (พอร์ต 8000)
    set BACKEND_RUNNING=1
)

REM ตรวจสอบ Frontend (port 3000)
netstat -ano | find ":3000" | find "LISTENING" > nul
if %ERRORLEVEL% EQU 0 (
    echo [STATUS] Frontend: กำลังทำงานอยู่แล้ว (พอร์ต 3000)
    set FRONTEND_RUNNING=1
)

REM ถ้าทุกบริการกำลังทำงาน ให้ถามผู้ใช้ว่าต้องการรีสตาร์ทหรือไม่
if %REDIS_RUNNING% EQU 1 if %BACKEND_RUNNING% EQU 1 if %FRONTEND_RUNNING% EQU 1 (
    echo.
    echo [INFO] ทุกบริการกำลังทำงานอยู่แล้ว
    set /p RESTART="คุณต้องการรีสตาร์ทบริการทั้งหมดหรือไม่? (Y/N): "
    if /i "!RESTART!"=="Y" (
        echo [INFO] กำลังรีสตาร์ทบริการทั้งหมด...
        
        REM หยุด Redis
        echo [INFO] กำลังหยุด Redis Server...
        taskkill /f /im redis-server.exe > nul 2>&1
        
        REM หยุด Backend (Python)
        echo [INFO] กำลังหยุด Backend API...
        for /f "tokens=5" %%a in ('netstat -ano ^| find ":8000" ^| find "LISTENING"') do (
            taskkill /f /pid %%a > nul 2>&1
        )
        
        REM หยุด Frontend (Node.js)
        echo [INFO] กำลังหยุด Frontend...
        for /f "tokens=5" %%a in ('netstat -ano ^| find ":3000" ^| find "LISTENING"') do (
            taskkill /f /pid %%a > nul 2>&1
        )
        
        REM รอให้กระบวนการต่างๆ หยุดทำงานสมบูรณ์
        timeout /t 3 > nul
        echo [INFO] หยุดบริการทั้งหมดแล้ว
    ) else (
        echo [INFO] ใช้บริการที่กำลังทำงานอยู่...
        echo.
        echo ======================================================
        echo    CRYPTO SIGNAL APP กำลังทำงาน! ใช้งานได้แล้วที่ http://localhost:3000
        echo ======================================================
        echo.
        echo [INFO] คำแนะนำ:
        echo   * จัดการสัญลักษณ์คริปโตด้วยคำสั่ง: crypto-symbol-manager.bat
        goto :eof
    )
)

echo [INFO] ตรวจสอบการติดตั้งที่จำเป็น...

REM ตรวจสอบ Python
where python >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] ไม่พบการติดตั้ง Python กรุณาติดตั้ง Python ก่อนใช้งาน
    goto :error_exit
)

REM ตรวจสอบ Node.js
where node >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] ไม่พบการติดตั้ง Node.js กรุณาติดตั้ง Node.js ก่อนใช้งาน
    goto :error_exit
)

REM ตรวจสอบการติดตั้ง Python packages
echo [INFO] ตรวจสอบ Python packages...
pip list | findstr fastapi >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [INFO] กำลังติดตั้ง Python dependencies...
    pip install -r requirements.txt
    if %ERRORLEVEL% NEQ 0 (
        echo [ERROR] การติดตั้ง dependencies ล้มเหลว
        goto :error_exit
    )
)

REM ตรวจสอบ Node modules
if not exist "%FRONTEND_DIR%\node_modules" (
    echo [INFO] กำลังติดตั้ง Node.js dependencies...
    cd "%FRONTEND_DIR%"
    call npm install
    if %ERRORLEVEL% NEQ 0 (
        echo [ERROR] การติดตั้ง Node.js dependencies ล้มเหลว
        goto :error_exit
    )
    cd "%APP_DIR%"
)

echo [INFO] การติดตั้งครบถ้วน
echo.

REM เริ่มต้น Redis Server (ถ้ายังไม่ได้เริ่มต้น)
if %REDIS_RUNNING% EQU 0 (
    echo [INFO] กำลังเริ่มต้น Redis Server...
    start "Redis Server" cmd /c "cd %REDIS_DIR% && redis-server.exe redis.windows.conf"
    ping -n 3 127.0.0.1 > nul
) else (
    echo [INFO] ใช้งาน Redis Server ที่กำลังทำงานอยู่
)

REM เริ่มต้น Backend Server (ถ้ายังไม่ได้เริ่มต้น)
if %BACKEND_RUNNING% EQU 0 (
    echo [INFO] กำลังเริ่มต้น Backend Server...
    start "Crypto Signal Backend" cmd /c "cd %BACKEND_DIR% && python main.py"
    ping -n 5 127.0.0.1 > nul

    REM ตรวจสอบว่า Backend ทำงานหรือไม่
    curl -s -o nul -w "%%{http_code}" http://localhost:8000/api/status > %TEMP%\status_code.txt
    set /p STATUS_CODE=<%TEMP%\status_code.txt
    del %TEMP%\status_code.txt

    if "!STATUS_CODE!" NEQ "200" (
        echo [WARNING] ไม่สามารถเข้าถึง Backend API ได้ อาจจะยังเริ่มต้นไม่เสร็จสมบูรณ์
        echo [INFO] รอให้ Backend พร้อมทำงาน...
        ping -n 10 127.0.0.1 > nul
    )
) else (
    echo [INFO] ใช้งาน Backend API ที่กำลังทำงานอยู่
)

REM เริ่มต้น Frontend Server (ถ้ายังไม่ได้เริ่มต้น)
if %FRONTEND_RUNNING% EQU 0 (
    echo [INFO] กำลังเริ่มต้น Frontend Server...
    start "Crypto Signal Frontend" cmd /c "cd %FRONTEND_DIR% && npm start"

    REM เปิดเว็บเบราวเซอร์หลังจากรอให้ Frontend พร้อม
    echo [INFO] กำลังรอให้ Frontend Server พร้อมทำงาน...
    ping -n 10 127.0.0.1 > nul
) else (
    echo [INFO] ใช้งาน Frontend ที่กำลังทำงานอยู่
)

echo [INFO] กำลังเปิดแอปพลิเคชัน...
start "" http://localhost:3000

echo.
echo ======================================================
echo    CRYPTO SIGNAL APP กำลังทำงาน! เปิดแอปพลิเคชันใน Browser แล้ว
echo ======================================================
echo.
echo [INFO] คำแนะนำ:
echo   * ปิดหน้าต่างคอมมานด์ไลน์เพื่อหยุดการทำงานของแอป
echo   * จัดการสัญลักษณ์คริปโตด้วยคำสั่ง: crypto-symbol-manager.bat

REM แสดงสถานะอีกครั้งหลังเริ่มต้นทั้งหมด
echo.
echo [INFO] สถานะระบบล่าสุด:
call :check_services

echo.
goto :eof

:check_services
REM ตรวจสอบสถานะบริการทั้งหมด
set SERVICE_ERRORS=0

REM ตรวจสอบ Redis
tasklist /fi "imagename eq redis-server.exe" | find "redis-server.exe" > nul
if %ERRORLEVEL% EQU 0 (
    echo [✓] Redis Server: กำลังทำงาน
) else (
    echo [✗] Redis Server: ไม่ได้ทำงาน
    set /a SERVICE_ERRORS+=1
)

REM ตรวจสอบ Backend API (port 8000)
netstat -ano | find ":8000" | find "LISTENING" > nul
if %ERRORLEVEL% EQU 0 (
    echo [✓] Backend API: กำลังทำงาน (พอร์ต 8000)
    REM ทดสอบการตอบสนองของ API
    curl -s -o nul -w "%%{http_code}" http://localhost:8000/ > %TEMP%\api_status.txt
    set /p API_STATUS=<%TEMP%\api_status.txt
    del %TEMP%\api_status.txt 2>nul
    
    if "!API_STATUS!"=="200" (
        echo [✓] Backend API: ตอบสนองปกติ
    ) else (
        echo [!] Backend API: ไม่ตอบสนอง (รหัสสถานะ: !API_STATUS!)
        set /a SERVICE_ERRORS+=1
    )
) else (
    echo [✗] Backend API: ไม่ได้ทำงาน
    set /a SERVICE_ERRORS+=1
)

REM ตรวจสอบ Frontend (port 3000)
netstat -ano | find ":3000" | find "LISTENING" > nul
if %ERRORLEVEL% EQU 0 (
    echo [✓] Frontend: กำลังทำงาน (พอร์ต 3000)
) else (
    echo [✗] Frontend: ไม่ได้ทำงาน
    set /a SERVICE_ERRORS+=1
)

exit /b %SERVICE_ERRORS%

:stop_all_services
REM หยุดการทำงานของทุกบริการ
set STOPPED_ANY=0

REM หยุด Frontend (Node.js)
echo [INFO] กำลังตรวจสอบ Frontend...
netstat -ano | find ":3000" | find "LISTENING" > nul
if %ERRORLEVEL% EQU 0 (
    for /f "tokens=5" %%a in ('netstat -ano ^| find ":3000" ^| find "LISTENING"') do (
        echo [INFO] กำลังหยุด Frontend (PID: %%a)...
        taskkill /f /pid %%a > nul 2>&1
        if !ERRORLEVEL! EQU 0 (
            echo [✓] หยุด Frontend สำเร็จ
            set STOPPED_ANY=1
        ) else (
            echo [✗] ไม่สามารถหยุด Frontend ได้
        )
    )
) else (
    echo [INFO] Frontend ไม่ได้ทำงานอยู่
)

REM หยุด Backend API (Python)
echo [INFO] กำลังตรวจสอบ Backend API...
netstat -ano | find ":8000" | find "LISTENING" > nul
if %ERRORLEVEL% EQU 0 (
    for /f "tokens=5" %%a in ('netstat -ano ^| find ":8000" ^| find "LISTENING"') do (
        echo [INFO] กำลังหยุด Backend API (PID: %%a)...
        taskkill /f /pid %%a > nul 2>&1
        if !ERRORLEVEL! EQU 0 (
            echo [✓] หยุด Backend API สำเร็จ
            set STOPPED_ANY=1
        ) else (
            echo [✗] ไม่สามารถหยุด Backend API ได้
        )
    )
) else (
    echo [INFO] Backend API ไม่ได้ทำงานอยู่
)

REM หยุด Redis Server
echo [INFO] กำลังตรวจสอบ Redis Server...
tasklist /fi "imagename eq redis-server.exe" | find "redis-server.exe" > nul
if %ERRORLEVEL% EQU 0 (
    echo [INFO] กำลังหยุด Redis Server...
    taskkill /f /im redis-server.exe > nul 2>&1
    if !ERRORLEVEL! EQU 0 (
        echo [✓] หยุด Redis Server สำเร็จ
        set STOPPED_ANY=1
    ) else (
        echo [✗] ไม่สามารถหยุด Redis Server ได้
    )
) else (
    echo [INFO] Redis Server ไม่ได้ทำงานอยู่
)

if %STOPPED_ANY% EQU 1 (
    echo.
    echo [INFO] หยุดบริการเสร็จสิ้น
) else (
    echo.
    echo [INFO] ไม่มีบริการที่กำลังทำงานอยู่
)

exit /b 0

:error_exit
echo.
echo [ERROR] การเริ่มต้นแอปพลิเคชันล้มเหลว โปรดแก้ไขปัญหาที่แสดงด้านบนแล้วลองอีกครั้ง
pause
exit /b 1
