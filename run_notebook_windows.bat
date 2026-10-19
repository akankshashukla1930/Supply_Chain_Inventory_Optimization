@echo off
REM Runs the full pipeline: cleaning -> DuckDB warehouse (+ query tests) -> run_sql -> executes the EDA notebook in place.
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo .venv not found - run setup_windows.bat first.
  pause
  exit /b 1
)
set PY=.venv\Scripts\python.exe
echo [1/4] Cleaning raw data ...
"%PY%" src\data_cleaning.py || goto :fail
echo [2/4] Building DuckDB warehouse and testing every query ...
"%PY%" scripts\build_warehouse.py || goto :fail
echo [3/4] Running SQL queries (results in outputs\sql_results) ...
"%PY%" scripts\run_sql.py --rows 5 || goto :fail
echo [4/4] Executing notebooks\01_EDA.ipynb ...
"%PY%" -m jupyter nbconvert --to notebook --execute --inplace notebooks\01_EDA.ipynb || goto :fail
echo.
echo All steps finished. Now open pbip\SupplyChain.pbip in Power BI Desktop (see pbip\OPEN_ME_FIRST.md).
pause
exit /b 0
:fail
echo A step FAILED - read the error above.
pause
exit /b 1
