@echo off
REM filepath: c:\Users\Nack\Documents\crypto-signal-app\test-services.bat
REM ===================================================================
REM ตรวจสอบสถานะของบริการทั้งหมด
REM ===================================================================
setlocal EnableDelayedExpansion

echo ======================================================
echo         CRYPTO SIGNAL APP - SERVICE TESTER
echo ======================================================
echo.

REM เก็บเวลาทดสอบ
set "TEST_TIMESTAMP=%DATE% %TIME%"
echo [INFO] เวลาทดสอบ: %TEST_TIMESTAMP%
echo.

set SERVICE_COUNT=0
set SERVICE_OK=0

REM ตรวจสอบ Redis
echo [TEST 1/3] Redis Server...
tasklist /fi "imagename eq redis-server.exe" 2>nul | find "redis-server.exe" > nul
set /a SERVICE_COUNT+=1
if %ERRORLEVEL% EQU 0 (
    echo [✓] Redis Server: OK
    set /a SERVICE_OK+=1
) else (
    echo [✗] Redis Server: FAILED
    echo [INFO] สาเหตุ: ไม่พบกระบวนการ redis-server.exe ในระบบ
)

REM ตรวจสอบ Backend API (port 8000)
echo.
echo [TEST 2/3] Backend API...
set /a SERVICE_COUNT+=1
netstat -ano 2>nul | find ":8000" | find "LISTENING" > nul
if %ERRORLEVEL% EQU 0 (
    echo [✓] Backend API ทำงานอยู่ที่พอร์ต 8000
    
    REM ทดสอบการตอบสนองของ API
    curl -s -o nul -m 5 -w "%%{http_code}" http://localhost:8000/api/status > %TEMP%\api_status.txt 2>nul
    if %ERRORLEVEL% EQU 0 (
        set /p API_STATUS=<%TEMP%\api_status.txt 2>nul
        del %TEMP%\api_status.txt 2>nul
    
        if "!API_STATUS!"=="200" (
            echo [✓] Backend API response: OK (HTTP !API_STATUS!)
            set /a SERVICE_OK+=1
        ) else (
            echo [!] Backend API response: ERROR (HTTP !API_STATUS!)
            echo [INFO] สาเหตุ: API ทำงานแต่ไม่ตอบสนองด้วยสถานะ 200 (ได้รับ !API_STATUS!)
            REM ลองทดสอบ API endpoint อื่น
            curl -s -o nul -m 5 -w "%%{http_code}" http://localhost:8000/ > %TEMP%\api_alt.txt 2>nul
            set /p API_ALT=<%TEMP%\api_alt.txt 2>nul
            del %TEMP%\api_alt.txt 2>nul
            if "!API_ALT!"=="200" (
                echo [✓] Backend API alternate endpoint: OK (HTTP !API_ALT!)
                set /a SERVICE_OK+=1
            )
        )
    ) else (
        echo [✗] Backend API response: FAILED (ไม่สามารถเชื่อมต่อได้)
        echo [INFO] สาเหตุ: API ทำงานแต่ไม่สามารถเข้าถึงได้ (curl ไม่สามารถทำงานได้)
    )
) else (
    echo [✗] Backend API: FAILED
    echo [INFO] สาเหตุ: ไม่พบบริการที่ทำงานอยู่บนพอร์ต 8000
)

REM ตรวจสอบ Frontend (port 3000)
echo.
echo [TEST 3/3] Frontend...
set /a SERVICE_COUNT+=1
netstat -ano 2>nul | find ":3000" | find "LISTENING" > nul
if %ERRORLEVEL% EQU 0 (
    echo [✓] Frontend ทำงานอยู่ที่พอร์ต 3000
    
    REM ทดสอบการตอบสนองของ Frontend
    curl -s -o nul -m 5 -w "%%{http_code}" http://localhost:3000/ > %TEMP%\frontend_status.txt 2>nul
    if %ERRORLEVEL% EQU 0 (
        set /p FRONTEND_STATUS=<%TEMP%\frontend_status.txt 2>nul
        del %TEMP%\frontend_status.txt 2>nul
    
        if "!FRONTEND_STATUS!"=="200" (
            echo [✓] Frontend response: OK (HTTP !FRONTEND_STATUS!)
            set /a SERVICE_OK+=1
        ) else (
            echo [!] Frontend response: ERROR (HTTP !FRONTEND_STATUS!)
            echo [INFO] สาเหตุ: Frontend ทำงานแต่ให้สถานะ HTTP !FRONTEND_STATUS!
        )
    ) else (
        echo [✗] Frontend response: FAILED (ไม่สามารถเชื่อมต่อได้)
        echo [INFO] สาเหตุ: Frontend อาจจะยังไม่พร้อมให้บริการ หรือกำลังโหลด
    )
) else (
    echo [✗] Frontend: FAILED
    echo [INFO] สาเหตุ: ไม่พบบริการที่ทำงานอยู่บนพอร์ต 3000
)

echo.
echo ======================================================
echo                     ผลการทดสอบ
echo ======================================================
echo [รายงาน] เวลาที่ทำการทดสอบ: %TEST_TIMESTAMP%
set /a SUCCESS_PERCENT=SERVICE_OK*100/SERVICE_COUNT
echo [รายงาน] ผลการทดสอบ: %SERVICE_OK%/%SERVICE_COUNT% บริการทำงานปกติ (%SUCCESS_PERCENT%%%)

if %SERVICE_OK% EQU %SERVICE_COUNT% (
    echo [สรุป] ✅ ผลการทดสอบ: สำเร็จ (ทุกบริการทำงานปกติ)
    echo [INFO] คุณสามารถเข้าใช้งานแอปพลิเคชันได้ที่: http://localhost:3000
) else (
    if %SERVICE_OK% GEQ 2 (
        echo [สรุป] 🟡 ผลการทดสอบ: เกือบสำเร็จ (บางบริการอาจยังไม่พร้อมให้บริการ)
        echo [INFO] คุณสามารถเข้าใช้งานแอปพลิเคชันได้ที่: http://localhost:3000
        echo [INFO] หมายเหตุ: หากพบปัญหาในการใช้งาน ให้รอสักครู่แล้วทดสอบใหม่
    ) else if %SERVICE_OK% GEQ 1 (
        echo [สรุป] ⚠️ ผลการทดสอบ: บางส่วน (บางบริการทำงานปกติ)
        echo [INFO] กรุณาแก้ไขปัญหาตามที่ระบุด้านบน
    ) else (
        echo [สรุป] ❌ ผลการทดสอบ: ล้มเหลว (ไม่มีบริการที่ทำงาน)
        echo [INFO] กรุณาเริ่มต้นระบบใหม่ทั้งหมด
    )
)

echo.
echo [INFO] คำแนะนำ:
echo   1. ใช้ start-all-components.bat เพื่อเริ่มบริการทั้งหมดใหม่
echo   2. ตรวจสอบไฟล์ log ใน logs/ เพื่อดูรายละเอียดข้อผิดพลาด

pause
exit /b 0
