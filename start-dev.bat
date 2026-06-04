@echo off
chcp 65001 >nul
echo.
echo  ==========================================
echo   SIEM-CORE - Entorno de desarrollo local
echo  ==========================================
echo.

cd /d "%~dp0"

echo [1/3] Iniciando Backend (FastAPI + SQLite)...
start "SIEM Backend" cmd /k "cd backend && .venv\Scripts\uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"

timeout /t 3 /nobreak >nul

echo [2/3] Iniciando Frontend (Vite)...
start "SIEM Frontend" cmd /k "cd frontend && npm run dev"

timeout /t 3 /nobreak >nul

echo [3/3] Iniciando Simulador de eventos...
start "SIEM Simulator" cmd /k "cd backend && .venv\Scripts\python simulator.py --rate 2"

echo.
echo  Backend:    http://localhost:8000
echo  Frontend:   http://localhost:5173
echo  Swagger:    http://localhost:8000/api/docs
echo.
echo  Credenciales demo: admin / Admin1234!
echo.
pause
