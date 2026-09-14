@echo off
REM Windows launcher: double-click this file to run the tool.
REM It finds the attached external drive, locates the GEO workbook on it,
REM hashes the data files and fills in the checksum column.
cd /d "%~dp0"
where py >nul 2>nul && set PY=py -3
if not defined PY where python >nul 2>nul && set PY=python
if not defined PY (
  echo Python 3 is not installed. Get it from https://www.python.org/downloads/
  pause
  exit /b 1
)
%PY% -c "import openpyxl" 2>nul || %PY% -m pip install --user -r requirements.txt
%PY% geo_checksum.py %*
echo.
pause
