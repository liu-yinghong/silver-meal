@echo off
set "BASE=%~dp0"
set "BASE=%BASE:~0,-1%"
set "TMP=%BASE%\tmp"
set "TEMP=%BASE%\tmp"
cd /d "%BASE%" 2>nul

echo ============================================
echo   Fan Xin - Silver Meal (Demo)
echo   Elder page : http://localhost:8000/elder/
echo   Family page: http://localhost:8000/family/
echo ============================================
echo.

REM ---- if port 8000 is already in use, tell the user ----
netstat -ano | findstr ":8000 " | findstr "LISTENING" >nul 2>nul
if %errorlevel%==0 goto :already_running

REM ---- find a python that has uvicorn ----
set "RUNNER="

REM 1. uvicorn command on PATH
where uvicorn >nul 2>nul
if not %errorlevel%==0 goto :try_python
set "RUNNER=uvicorn app.main:app --host 0.0.0.0 --port 8000"
goto :run

REM 2. python -m uvicorn
:try_python
where python >nul 2>nul
if not %errorlevel%==0 goto :try_anaconda
set "RUNNER=python -m uvicorn app.main:app --host 0.0.0.0 --port 8000"
goto :run

REM 3. this machine Anaconda python
:try_anaconda
if not exist "D:\python.package\anaconda\python.exe" goto :fail
set "RUNNER=D:\python.package\anaconda\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000"
goto :run

:already_running
echo.
echo [INFO] Port 8000 is already in use.
echo The server may already be running.
echo Opening the elder page now...
start "" "http://localhost:8000/elder/"
echo.
pause
exit /b 0

:fail
echo.
echo [ERROR] uvicorn / python was not found.
echo Please install dependencies first:
echo     pip install -r requirements.txt
echo.
pause
exit /b 1

:run
echo Starting... press Ctrl+C to stop.
echo.
%RUNNER%

echo.
echo Server stopped. If there are errors above, please report them.
pause
