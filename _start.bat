@echo off
set "BASE=%~dp0"
set "BASE=%BASE:~0,-1%"
cd /d "%BASE%" 2>nul

echo ============================================
echo   Fan Xin - Silver Meal (Demo)
echo   Elder page : http://localhost:8000/elder/
echo   Family page: http://localhost:8000/family/
echo ============================================
echo.

REM ---- if port 8000 is already in use, inform the user ----
netstat -ano | findstr ":8000 " | findstr "LISTENING" >nul 2>nul
if %errorlevel%==0 goto :already_running

REM ---- find a python interpreter ----
set "PY="
where python >nul 2>nul
if %errorlevel%==0 set "PY=python"
if not defined PY (
  where py >nul 2>nul
  if %errorlevel%==0 set "PY=py -3"
)
if not defined PY (
  if exist "D:\python.package\anaconda\python.exe" set "PY=D:\python.package\anaconda\python.exe"
)
if not defined PY goto :no_python

REM ---- verify the python interpreter actually runs (Windows Store alias check) ----
%PY% -V >nul 2>nul
if %errorlevel% neq 0 goto :bad_python

REM ---- check if uvicorn is installed ----
%PY% -c "import uvicorn" >nul 2>nul
if %errorlevel%==0 goto :start

REM ---- not installed: auto install dependencies ----
echo.
echo [SETUP] First run: installing dependencies, please wait...
%PY% -m pip install -r requirements.txt
%PY% -c "import uvicorn" >nul 2>nul
if %errorlevel%==0 goto :start

echo.
echo [ERROR] Failed to install dependencies automatically.
echo Please run manually:
echo     %PY% -m pip install -r requirements.txt
echo.
pause
exit /b 1

:start
echo Starting... press Ctrl+C to stop.
echo.
%PY% -m uvicorn app.main:app --host 0.0.0.0 --port 8000

echo.
echo Server stopped. If there are errors above, please report them.
pause
exit /b 0

:already_running
echo.
echo [INFO] Port 8000 is already in use.
echo The server may already be running.
start "" "http://localhost:8000/elder/"
echo.
pause
exit /b 0

:no_python
echo.
echo [ERROR] Python was not found.
echo Please install Python 3.10+ first:
echo     https://www.python.org/downloads/
echo (during install, tick "Add Python to PATH")
echo Then run this file again.
echo.
pause
exit /b 1

:bad_python
echo.
echo [ERROR] Python was found but cannot run properly.
echo This usually means Windows "app execution alias" is pointing "python"
echo to the Microsoft Store placeholder, or no real Python is installed.
echo.
echo Fix steps:
echo   1) Settings - Apps - Advanced app settings - App execution aliases,
echo      turn OFF "python.exe" and "python3.exe";
echo   2) install real Python 3.10+ from https://www.python.org/downloads/
echo      (tick "Add Python to PATH" during install).
echo Then run this file again.
echo.
pause
exit /b 1
