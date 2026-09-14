#!/bin/bash
# macOS launcher: double-click this file in Finder to run the tool.
# It finds the attached external drive, locates the GEO workbook on it,
# hashes the data files and fills in the checksum column.
cd "$(dirname "$0")"
PY=$(command -v python3 || command -v python)
if [ -z "$PY" ]; then
  echo "Python 3 is not installed. Get it from https://www.python.org/downloads/"
  read -r -p "Press Enter to close."
  exit 1
fi
"$PY" -c "import openpyxl" 2>/dev/null || "$PY" -m pip install --user -r requirements.txt
"$PY" geo_checksum.py "$@"
echo
read -r -p "Press Enter to close."
