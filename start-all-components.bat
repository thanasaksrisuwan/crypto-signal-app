@echo off
REM filepath: c:\Users\Nack\Documents\crypto-signal-app\start-all-components.bat
REM ===================================================================
REM เริ่มต้นบริการทั้งหมด
REM ===================================================================
setlocal EnableDelayedExpansion

echo ======================================================
echo       CRYPTO SIGNAL APP - COMPONENT STARTER
echo ======================================================
echo.

REM ตั้งค่าตำแหน่งของไดเรกทอรี่
set "APP_DIR=%~dp0"
cd %APP_DIR%

echo [1/3] กำลังเริ่มต้น Redis Server...
cd "%APP_DIR%redis"
start "Redis Server" redis-server.exe redis.windows.conf
cd %APP_DIR%
echo [✓] เริ่ม Redis Server แล้ว
timeout /t 3 > nul

echo [2/3] กำลังเริ่มต้น Backend API...
cd "%APP_DIR%app"
start "Crypto Signal Backend" python main.py
cd %APP_DIR%
echo [✓] เริ่ม Backend API แล้ว
timeout /t 5 > nul

echo [3/3] กำลังเริ่มต้น Frontend...
cd "%APP_DIR%frontend"
start "Crypto Signal Frontend" npm start
cd %APP_DIR%
echo [✓] เริ่ม Frontend แล้ว
timeout /t 10 > nul

echo.
echo ======================================================
echo    CRYPTO SIGNAL APP กำลังทำงาน! เปิดแอปพลิเคชันใน Browser
echo ======================================================
echo.

echo [INFO] กำลังเปิดแอปพลิเคชัน...
start "" http://localhost:3000

echo [INFO] ข้อมูลเพิ่มเติม:
echo   - ตรวจสอบสถานะ: start-crypto-app.bat status
echo   - หยุดบริการ: start-crypto-app.bat stop
echo   - จัดการสัญลักษณ์คริปโต: crypto-symbol-manager.bat

echo.
echo [NOTE] กด Ctrl+C เพื่อปิดหน้าต่างนี้ โดยที่บริการต่างๆ จะยังคงทำงานต่อไป
echo.
cmd /k
