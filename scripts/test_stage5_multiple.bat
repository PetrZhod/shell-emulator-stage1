@echo off
cd /d "%~dp0.."
if not exist logs mkdir logs
copy /Y "examples\multiple.json" "logs\multiple.json" >nul
python src\main.py --vfs "logs\multiple.json" --log "logs\stage5_multiple.csv" --script "examples\startup.txt"
