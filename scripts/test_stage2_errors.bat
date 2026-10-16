@echo off
setlocal
cd /d "%~dp0.."
echo Missing startup script: close the GUI to continue.
python src\main.py --vfs "examples\vfs.json" --log "logs\missing-script.csv" --script "examples\missing.txt"
echo Invalid log path: using an existing directory instead of a file.
python src\main.py --vfs "examples\vfs.json" --log "examples" --script "examples\startup.txt"
echo Missing option value: argparse must report an error.
python src\main.py --vfs "examples\vfs.json" --log "logs\args.csv" --script
echo Unknown option: argparse must report an error.
python src\main.py --vfs "examples\vfs.json" --log "logs\args.csv" --script "examples\startup.txt" --unknown
pause
endlocal
