@echo off
setlocal
cd /d "%~dp0.."
python src\main.py --vfs "examples\vfs.json" --log "logs\exit.csv" --script "examples\exit.txt"
echo The CSV must contain ls and exit, but not must-not-run.
pause
endlocal
