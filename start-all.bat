@echo off
REM ======================================================================
REM Crypto Signal App - Start All Components
REM เริ่มต้นระบบทั้งหมดพร้อมกัน (Redis, Backend, Frontend)
REM ======================================================================

setlocal enabledelayedexpansion

echo.
echo ====== เริ่มต้นระบบทั้งหมด ======
echo.

REM ตั้งค่าตัวแปรพื้นฐาน
set "SCRIPT_DIR=%~dp0"

REM เริ่มต้น Redis
echo กำลังเริ่มต้น Redis...
call "%SCRIPT_DIR%start-redis.bat"
REM รอให้ Redis เริ่มต้นเสร็จ
timeout /t 3 > nul

REM เริ่มต้น Backend API
echo.
echo กำลังเริ่มต้น Backend API...
call "%SCRIPT_DIR%start-backend.bat"
REM รอให้ Backend API เริ่มต้นเสร็จ
timeout /t 5 > nul

REM เริ่มต้น Frontend
echo.
echo กำลังเริ่มต้น Frontend...
call "%SCRIPT_DIR%start-frontend.bat"

echo.
echo ====== เริ่มต้นระบบทั้งหมดเสร็จสมบูรณ์ ======
echo.
echo เข้าใช้งานแอปพลิเคชันได้ที่ http://localhost:3000
echo API Documentation มีให้บริการที่ http://localhost:8000/docs
echo.

endlocal