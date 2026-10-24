@echo off
cd /d "%~dp0.."
if not exist logs mkdir logs
copy /Y "examples\deep.json" "logs\deep.json" >nul
python src\main.py --vfs "logs\deep.json" --log "logs\stage5_deep.csv" --script "examples\startup.txt"
