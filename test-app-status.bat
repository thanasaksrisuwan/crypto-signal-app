@echo off
REM filepath: c:\Users\Nack\Documents\crypto-signal-app\test-app-status.bat
REM ===================================================================
REM ทดสอบสถานะของบริการต่างๆ ในระบบ Crypto Signal App
REM ===================================================================
setlocal EnableDelayedExpansion

echo ======================================================
echo         CRYPTO SIGNAL APP - SERVICE TESTER
echo ======================================================
echo.

REM ตรวจสอบสถานะบริการทั้งหมด
set "SERVICE_ERRORS=0"

REM ตรวจสอบ Redis
echo [INFO] กำลังตรวจสอบ Redis Server...
tasklist /fi "imagename eq redis-server.exe" 2>nul | find "redis-server.exe" > nul
if %ERRORLEVEL% EQU 0 (
    echo [✓] Redis Server: กำลังทำงาน
) else (
    echo [✗] Redis Server: ไม่ได้ทำงาน
    set /a SERVICE_ERRORS+=1
)

REM ตรวจสอบ Backend API (port 8000)
echo [INFO] กำลังตรวจสอบ Backend API...
netstat -ano 2>nul | find ":8000" | find "LISTENING" > nul
if %ERRORLEVEL% EQU 0 (
    echo [✓] Backend API: กำลังทำงาน (พอร์ต 8000)
    
    REM ทดสอบการตอบสนองของ API
    echo [INFO] กำลังทดสอบการตอบสนองของ API...
    curl -s -o nul -w "%%{http_code}" http://localhost:8000/api/status > %TEMP%\api_status.txt 2>nul
    set /p API_STATUS=<%TEMP%\api_status.txt 2>nul
    del %TEMP%\api_status.txt 2>nul
    
    if "!API_STATUS!"=="200" (
        echo [✓] Backend API: ตอบสนองปกติ (สถานะ: !API_STATUS!)
    ) else (
        echo [!] Backend API: ไม่ตอบสนองหรือมีปัญหา (สถานะ: !API_STATUS!)
        set /a SERVICE_ERRORS+=1
    )
) else (
    echo [✗] Backend API: ไม่ได้ทำงาน
    set /a SERVICE_ERRORS+=1
)

REM ตรวจสอบ Frontend (port 3000)
echo [INFO] กำลังตรวจสอบ Frontend...
netstat -ano 2>nul | find ":3000" | find "LISTENING" > nul
if %ERRORLEVEL% EQU 0 (
    echo [✓] Frontend: กำลังทำงาน (พอร์ต 3000)
    
    REM ทดสอบการตอบสนองของ Frontend
    echo [INFO] กำลังทดสอบการตอบสนองของ Frontend...
    curl -s -o nul -w "%%{http_code}" http://localhost:3000/ > %TEMP%\frontend_status.txt 2>nul
    set /p FRONTEND_STATUS=<%TEMP%\frontend_status.txt 2>nul
    del %TEMP%\frontend_status.txt 2>nul
    
    if "!FRONTEND_STATUS!"=="200" (
        echo [✓] Frontend: ตอบสนองปกติ (สถานะ: !FRONTEND_STATUS!)
    ) else (
        echo [!] Frontend: ไม่ตอบสนองหรือมีปัญหา (สถานะ: !FRONTEND_STATUS!)
        set /a SERVICE_ERRORS+=1
    )
) else (
    echo [✗] Frontend: ไม่ได้ทำงาน
    set /a SERVICE_ERRORS+=1
)

echo.
echo [สรุป] พบบริการที่มีปัญหา: %SERVICE_ERRORS%
if %SERVICE_ERRORS% EQU 0 (
    echo [สรุป] ทุกบริการทำงานปกติ!
    echo.
    echo ✅ คุณสามารถเข้าใช้งานแอปพลิเคชันได้ที่: http://localhost:3000
) else (
    echo [สรุป] พบปัญหาในบางบริการ กรุณาตรวจสอบและแก้ไข
    echo.
    echo 📌 คำแนะนำในการแก้ไข:
    echo   1. ใช้คำสั่ง start-crypto-app.bat เพื่อเริ่มระบบทั้งหมดอีกครั้ง
    echo   2. ตรวจสอบไฟล์ log ใน logs/ สำหรับรายละเอียดของข้อผิดพลาด
)

echo.
echo [INFO] คุณสามารถใช้คำสั่งต่อไปนี้:
echo   • start-crypto-app.bat        - เริ่มบริการทั้งหมด
echo   • start-crypto-app.bat status - ดูสถานะบริการทั้งหมด
echo   • start-crypto-app.bat stop   - หยุดบริการทั้งหมด
echo   • crypto-symbol-manager.bat   - จัดการสัญลักษณ์คริปโต

pause
exit /b %SERVICE_ERRORS%
