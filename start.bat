@echo off
chcp 65001 >nul
title Kutubxona
cd /d "%~dp0"
where python >nul 2>nul || (echo Python o'rnatilmagan. https://www.python.org/downloads/ dan o'rnating. & pause & exit /b 1)
if not exist venv (
  echo Birinchi marta: kerakli narsalar o'rnatilmoqda, bir necha daqiqa kuting...
  python -m venv venv
)
if not exist venv\Lib\site-packages\uvicorn (
  venv\Scripts\python.exe -m pip install -r requirements.txt
)
if not exist .env (
  echo.
  echo Admin parolini o'ylab toping (kamida 10 belgi; & ^ %% belgilarini ishlatmang).
  set /p PW=Parol: 
  (echo ADMIN_USER=admin& echo ADMIN_PASSWORD=%PW%& echo APP_ENV=development)>.env
)
start "" "http://localhost:8000"
echo.
echo Sayt:  http://localhost:8000
echo Admin: http://localhost:8000/admin  (login: admin, parol: .env faylida)
echo Telefondan kirish: ipconfig orqali IPv4 ni oling: http://IP:8000
echo To'xtatish uchun shu oynani yoping yoki Ctrl+C bosing.
echo.
venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8000
pause
