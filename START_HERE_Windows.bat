@echo off
setlocal
title GEO checksum tool
cd /d "%~dp0"

set "PY="
py -3 -c "import sys" >nul 2>&1 && set "PY=py -3"
if not defined PY python -c "import sys" >nul 2>&1 && set "PY=python"
if defined PY goto :have_python

echo Python is not on this computer yet. Installing it now (this takes a minute or two).
echo If a window asks for permission, click Yes.
echo.
winget install -e --id Python.Python.3.12 --scope user --silent --accept-package-agreements --accept-source-agreements
if errorlevel 1 winget install -e --id Python.Python.3.12 --silent --accept-package-agreements --accept-source-agreements
if errorlevel 1 goto :no_python

echo.
echo Python is installed. Please close this window and double-click START_HERE_Windows.bat again.
pause
exit /b 0

:no_python
echo.
echo Python could not be installed automatically.
echo 1. Go to https://www.python.org/downloads/ and click "Download Python".
echo 2. Run the installer and tick the box "Add python.exe to PATH".
echo 3. Double-click START_HERE_Windows.bat again.
pause
exit /b 1

:have_python
%PY% -c "import openpyxl" >nul 2>&1
if errorlevel 1 (
    echo Setting up, one moment...
    %PY% -m pip install --user --quiet --disable-pip-version-check openpyxl >nul 2>&1
    if errorlevel 1 %PY% -m pip install --quiet --disable-pip-version-check openpyxl
)
%PY% geo_checksum.py
echo.
pause
