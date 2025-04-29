@echo off
REM ======================================================================
REM Backend API Starter
REM เริ่มต้น Backend API สำหรับแอป Crypto Signal
REM ======================================================================

setlocal enabledelayedexpansion

echo.
echo ====== เริ่มต้น Backend API ======
echo.

REM ตั้งค่าตัวแปรพื้นฐาน
set "SCRIPT_DIR=%~dp0"
set "APP_DIR=%SCRIPT_DIR%app"
set "VIRTUAL_ENV=%SCRIPT_DIR%venv"
set "LOG_DIR=%SCRIPT_DIR%logs"

REM ตรวจสอบว่าโฟลเดอร์แอปมีอยู่หรือไม่
if not exist "%APP_DIR%" (
    echo ไม่พบโฟลเดอร์แอป ที่ %APP_DIR%
    echo โปรดตรวจสอบโครงสร้างโปรเจกต์
    goto :eof
)

REM ตรวจสอบว่ามี Virtual Environment หรือไม่
if not exist "%VIRTUAL_ENV%" (
    echo ไม่พบ Virtual Environment ที่ %VIRTUAL_ENV%
    echo กำลังสร้าง Virtual Environment...
    python -m venv "%VIRTUAL_ENV%"
    
    if not exist "%VIRTUAL_ENV%" (
        echo ไม่สามารถสร้าง Virtual Environment ได้
        echo โปรดติดตั้ง Python 3.8 หรือใหม่กว่า
        goto :eof
    )
    
    echo ติดตั้ง dependencies...
    call "%VIRTUAL_ENV%\Scripts\activate.bat"
    pip install -r "%SCRIPT_DIR%requirements.txt"
)

REM สร้างโฟลเดอร์ logs ถ้ายังไม่มี
if not exist "%LOG_DIR%" (
    mkdir "%LOG_DIR%"
    echo สร้างโฟลเดอร์ %LOG_DIR% สำเร็จ
)

REM ตรวจสอบว่า Backend API กำลังทำงานอยู่หรือไม่
tasklist /fi "imagename eq python.exe" | find "python.exe" > nul
if %errorlevel% equ 0 (
    REM มีกระบวนการ Python ทำงานอยู่ แต่อาจไม่ใช่ API ของเรา
    REM ตรวจสอบว่าพอร์ต 8000 ถูกใช้งานอยู่หรือไม่
    netstat -ano | find ":8000" | find "LISTENING" > nul
    if %errorlevel% equ 0 (
        echo Backend API อาจกำลังทำงานอยู่แล้ว (พอร์ต 8000 ถูกใช้งาน)
        goto :ask_restart
    )
)

:start_backend
REM เริ่มต้น Backend API
echo เริ่มต้น Backend API...

REM เรียกใช้ virtual environment
call "%VIRTUAL_ENV%\Scripts\activate.bat"

REM ตรวจสอบว่า Redis กำลังทำงานอยู่หรือไม่
tasklist /fi "imagename eq redis-server.exe" | find "redis-server.exe" > nul
if %errorlevel% neq 0 (
    echo คำเตือน: Redis Server ไม่ได้ทำงานอยู่
    echo แนะนำให้เริ่มต้น Redis ก่อนด้วยคำสั่ง start-redis.bat
    echo.
    set /p continue="คุณต้องการดำเนินการต่อหรือไม่? (Y/N): "
    if /i not "%continue%"=="Y" goto :eof
)

echo กำลังเริ่มต้น Backend API...
echo ข้อมูลจะถูกบันทึกไว้ที่ %LOG_DIR%\backend.log

REM เริ่มต้น Backend API และบันทึกผลลัพธ์ลงในไฟล์ log
start "Backend API" cmd /c "call "%VIRTUAL_ENV%\Scripts\activate.bat" && cd "%APP_DIR%" && python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload > "%LOG_DIR%\backend.log" 2>&1"

echo Backend API เริ่มต้นแล้ว!
echo เปิด browser ที่ http://localhost:8000 เพื่อเข้าถึง API
echo.
goto :eof

:ask_restart
echo.
set /p restart="Backend API อาจกำลังทำงานอยู่แล้ว คุณต้องการรีสตาร์ทหรือไม่? (Y/N): "
if /i "%restart%"=="Y" (
    echo กำลังรีสตาร์ท Backend API...
    
    REM ค้นหา PID ของกระบวนการที่ใช้พอร์ต 8000
    for /f "tokens=5" %%a in ('netstat -ano ^| find ":8000" ^| find "LISTENING"') do (
        echo ยกเลิกกระบวนการ %%a
        taskkill /f /pid %%a > nul 2>&1
    )
    
    timeout /t 2 > nul
    goto :start_backend
) else (
    echo ไม่มีการเปลี่ยนแปลง Backend API ยังคงทำงานต่อไป
)

:eof
endlocal