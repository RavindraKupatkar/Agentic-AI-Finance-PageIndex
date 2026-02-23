@echo off
REM =============================================
REM  Finance RAG - Start Both Servers
REM  Backend (FastAPI) + Frontend (Vite React)
REM =============================================

echo.
echo  ============================================
echo   Finance RAG - Starting All Servers
echo  ============================================
echo.

REM -- Start Backend (FastAPI on port 8000) ------
echo [1/2] Starting Backend Server (FastAPI)...
cd /d "%~dp0"
start "Backend - FastAPI" cmd /k "cd /d "%~dp0" && call venv\Scripts\activate && python main.py server"

REM -- Give backend a moment to boot ------
timeout /t 3 /nobreak >nul

REM -- Start Frontend (Vite on port 5173) ------
echo [2/2] Starting Frontend Server (Vite)...
start "Frontend - Vite" cmd /k "cd /d "%~dp0frontend" && npm run dev"

echo.
echo  ============================================
echo   Both servers are starting!
echo  ============================================
echo.
echo   Backend  : http://localhost:8000
echo   Frontend : http://localhost:5173
echo.
echo   Close the opened terminal windows to stop.
echo  ============================================
echo.
