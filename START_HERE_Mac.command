#!/bin/bash
# Double-click this file. If macOS says it "cannot be opened", right-click it
# and choose Open the first time.
cd "$(dirname "$0")"

find_python() {
  for c in python3 python; do
    if command -v "$c" >/dev/null 2>&1 &&
       "$c" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)' >/dev/null 2>&1; then
      echo "$c"; return 0
    fi
  done
  return 1
}

PY=$(find_python)
if [ -z "$PY" ]; then
  echo "Python is not on this Mac yet."
  echo "1. Open https://www.python.org/downloads/ and click 'Download Python'."
  echo "2. Run the installer."
  echo "3. Double-click START_HERE_Mac.command again."
  open "https://www.python.org/downloads/" 2>/dev/null
  read -r -p "Press Enter to close."
  exit 1
fi

"$PY" -c "import openpyxl" 2>/dev/null || {
  echo "Setting up, one moment..."
  "$PY" -m pip install --user --quiet --disable-pip-version-check openpyxl 2>/dev/null ||
  "$PY" -m pip install --quiet --disable-pip-version-check openpyxl
}
"$PY" geo_checksum.py
echo
read -r -p "Press Enter to close."
