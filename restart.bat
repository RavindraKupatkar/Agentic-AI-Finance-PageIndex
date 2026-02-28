@echo off
REM =============================================
REM  FinSight AI — Restart Both Servers
REM =============================================

echo.
echo  ============================================
echo   FinSight AI - Restarting All Servers
echo  ============================================
echo.

REM ─── Step 1: Kill existing processes ───────────────────────

echo [1/4] Terminating Backend Server on port 8000...
set "KILLED_BACKEND=0"
FOR /F "tokens=5" %%a IN ('netstat -aon ^| find ":8000" ^| find "LISTENING"') DO (
    taskkill /F /PID %%a >nul 2>&1
    echo       Killed PID: %%a
    set "KILLED_BACKEND=1"
)
IF "%KILLED_BACKEND%"=="0" echo       No backend process found on port 8000.

echo [2/4] Terminating Frontend Server on port 3000...
set "KILLED_FRONTEND=0"
FOR /F "tokens=5" %%a IN ('netstat -aon ^| find ":3000" ^| find "LISTENING"') DO (
    taskkill /F /PID %%a >nul 2>&1
    echo       Killed PID: %%a
    set "KILLED_FRONTEND=1"
)
IF "%KILLED_FRONTEND%"=="0" echo       No frontend process found on port 3000.

echo.
echo Waiting for ports to be freed...
timeout /t 2 /nobreak >nul

REM ─── Step 2: Start Backend ─────────────────────────────────

echo.
echo [3/4] Starting Backend (FastAPI on port 8000)...

REM Activate venv and run the server in a new window
start "FinSight Backend" cmd /k "cd /d %~dp0 && call venv\Scripts\activate.bat && python main.py server"

echo       Backend starting in a new window.

REM ─── Step 3: Start Frontend ────────────────────────────────

echo [4/4] Starting Frontend (Next.js on port 3000)...

start "FinSight Frontend" cmd /k "cd /d %~dp0finsight-frontend && npm run dev"

echo       Frontend starting in a new window.

REM ─── Done ──────────────────────────────────────────────────

echo.
echo  ============================================
echo   All servers launched!
echo  ============================================
echo.
echo   Backend:   http://localhost:8000
echo   Frontend:  http://localhost:3000
echo   API Docs:  http://localhost:8000/docs
echo.
echo   (This window can be closed safely)
echo.
pause
