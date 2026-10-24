@echo off
cd /d "%~dp0.."
if not exist logs mkdir logs
copy /Y "examples\minimal.json" "logs\minimal.json" >nul
python src\main.py --vfs "logs\minimal.json" --log "logs\stage4_minimal.csv" --script "examples\startup.txt"
