@echo off
setlocal
cd /d "%~dp0.."
if not exist "logs\space demo" mkdir "logs\space demo"
copy /y "examples\startup.txt" "logs\space demo\startup script.txt" >nul
copy /y "examples\vfs.json" "logs\space demo\virtual fs.json" >nul
python src\main.py --vfs "logs\space demo\virtual fs.json" --log "logs\space demo\commands log.csv" --script "logs\space demo\startup script.txt"
endlocal
