@echo off
chcp 65001 >nul
set "BASE=%~dp0"
set "TMP=%BASE%tmp"
set "TEMP=%BASE%tmp"
cd /d "%BASE%"

echo ============================================
echo   饭心 · 银龄放心单 正在启动...
echo   老人端: http://localhost:8000/elder/
echo   家属端: http://localhost:8000/family/
echo ============================================
echo.

REM ---- 依次尝试可用的启动方式 ----

where python >nul 2>nul
if not %errorlevel%==0 goto :try_uvicorn
echo [方式1] python -m uvicorn
set "CMD=python -m uvicorn app.main:app --host 0.0.0.0 --port 8000"
goto :run

:try_uvicorn
where uvicorn >nul 2>nul
if not %errorlevel%==0 goto :no_uvicorn
echo [方式2] uvicorn
set "CMD=uvicorn app.main:app --host 0.0.0.0 --port 8000"
goto :run

:no_uvicorn
echo.
echo [错误] 未找到 python 或 uvicorn。
echo 请先安装依赖后重试：
echo     pip install -r requirements.txt
echo.
pause
exit /b 1

:run
echo 启动中... 按 Ctrl+C 停止服务
echo.
%CMD%

echo.
echo 服务已停止。若上方出现错误，请截图反馈。
pause
