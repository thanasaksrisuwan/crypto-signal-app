@echo off
REM filepath: c:\Users\Nack\Documents\crypto-signal-app\start-redis.bat
REM ===================================================================
REM เริ่มต้น Redis Server
REM ===================================================================

echo [INFO] กำลังเริ่มต้น Redis Server...

cd "%~dp0redis"
start "Redis Server" redis-server.exe redis.windows.conf

echo [✓] เริ่มต้น Redis Server แล้ว
pause
