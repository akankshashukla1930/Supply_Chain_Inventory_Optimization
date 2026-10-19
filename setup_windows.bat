@echo off
REM Supply Chain & Inventory Optimization - one-time setup on Windows
REM Creates .venv with the Python launcher (py -3), installs requirements and registers a Jupyter kernel.
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  echo Python launcher "py" not found. Install Python 3.10+ from python.org and tick "Add python.exe to PATH".
  pause
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
  echo Creating virtual environment .venv ...
  py -3 -m venv .venv
  if errorlevel 1 goto :fail
)
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :fail
".venv\Scripts\python.exe" -m ipykernel install --user --name supply-chain --display-name "Python (supply-chain)"
echo.
echo Setup complete. Next: run_notebook_windows.bat
pause
exit /b 0
:fail
echo Setup FAILED - read the error above.
pause
exit /b 1
