@echo off
REM ======================================================================
REM Frontend Starter
REM เริ่มต้น Frontend React สำหรับแอป Crypto Signal
REM ======================================================================

setlocal enabledelayedexpansion

echo.
echo ====== เริ่มต้น Frontend React ======
echo.

REM ตั้งค่าตัวแปรพื้นฐาน
set "SCRIPT_DIR=%~dp0"
set "FRONTEND_DIR=%SCRIPT_DIR%frontend"
set "LOG_DIR=%SCRIPT_DIR%logs"

REM ตรวจสอบว่าโฟลเดอร์ Frontend มีอยู่หรือไม่
if not exist "%FRONTEND_DIR%" (
    echo ไม่พบโฟลเดอร์ Frontend ที่ %FRONTEND_DIR%
    echo โปรดตรวจสอบโครงสร้างโปรเจกต์
    goto :eof
)

REM ตรวจสอบว่ามีไฟล์ package.json หรือไม่
if not exist "%FRONTEND_DIR%\package.json" (
    echo ไม่พบไฟล์ package.json ในโฟลเดอร์ Frontend
    echo โปรดตรวจสอบการติดตั้ง React
    goto :eof
)

REM สร้างโฟลเดอร์ logs ถ้ายังไม่มี
if not exist "%LOG_DIR%" (
    mkdir "%LOG_DIR%"
    echo สร้างโฟลเดอร์ %LOG_DIR% สำเร็จ
)

REM ตรวจสอบว่า Node.js ติดตั้งหรือไม่
node --version > nul 2>&1
if %errorlevel% neq 0 (
    echo ไม่พบการติดตั้ง Node.js
    echo โปรดติดตั้ง Node.js สำหรับ Frontend
    goto :eof
)

REM ตรวจสอบว่า npm ติดตั้งหรือไม่
npm --version > nul 2>&1
if %errorlevel% neq 0 (
    echo ไม่พบการติดตั้ง npm
    echo โปรดติดตั้ง Node.js และ npm สำหรับ Frontend
    goto :eof
)

REM ตรวจสอบว่ามีโฟลเดอร์ node_modules หรือไม่
if not exist "%FRONTEND_DIR%\node_modules" (
    echo ไม่พบโฟลเดอร์ node_modules ในโฟลเดอร์ Frontend
    echo กำลังติดตั้ง dependencies...
    cd "%FRONTEND_DIR%"
    npm install
)

REM ตรวจสอบว่า Frontend กำลังทำงานอยู่หรือไม่
netstat -ano | find ":3000" | find "LISTENING" > nul
if %errorlevel% equ 0 (
    echo Frontend อาจกำลังทำงานอยู่แล้ว (พอร์ต 3000 ถูกใช้งาน)
    goto :ask_restart
)

:start_frontend
REM ตรวจสอบว่า Backend API กำลังทำงานอยู่หรือไม่
netstat -ano | find ":8000" | find "LISTENING" > nul
if %errorlevel% neq 0 (
    echo คำเตือน: Backend API ไม่ได้ทำงานอยู่ (พอร์ต 8000 ไม่ได้ถูกใช้งาน)
    echo แนะนำให้เริ่มต้น Backend API ก่อนด้วยคำสั่ง start-backend.bat
    echo.
    set /p continue="คุณต้องการดำเนินการต่อหรือไม่? (Y/N): "
    if /i not "%continue%"=="Y" goto :eof
)

echo กำลังเริ่มต้น Frontend...
echo ข้อมูลจะถูกบันทึกไว้ที่ %LOG_DIR%\frontend.log

REM เริ่มต้น Frontend และบันทึกผลลัพธ์ลงในไฟล์ log
cd "%FRONTEND_DIR%"
start "Frontend" cmd /c "npm start > "%LOG_DIR%\frontend.log" 2>&1"

echo Frontend เริ่มต้นแล้ว!
echo เปิด browser ที่ http://localhost:3000 เพื่อเข้าใช้งานแอปพลิเคชัน
echo.
goto :eof

:ask_restart
echo.
set /p restart="Frontend อาจกำลังทำงานอยู่แล้ว คุณต้องการรีสตาร์ทหรือไม่? (Y/N): "
if /i "%restart%"=="Y" (
    echo กำลังรีสตาร์ท Frontend...
    
    REM ค้นหา PID ของกระบวนการที่ใช้พอร์ต 3000
    for /f "tokens=5" %%a in ('netstat -ano ^| find ":3000" ^| find "LISTENING"') do (
        echo ยกเลิกกระบวนการ %%a
        taskkill /f /pid %%a > nul 2>&1
    )
    
    timeout /t 2 > nul
    goto :start_frontend
) else (
    echo ไม่มีการเปลี่ยนแปลง Frontend ยังคงทำงานต่อไป
)

:eof
endlocal