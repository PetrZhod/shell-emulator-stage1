@echo off
setlocal
cd /d "%~dp0.."
python src\main.py --vfs "examples\vfs.json" --log "logs\basic.csv" --script "examples\startup.txt"
endlocal
