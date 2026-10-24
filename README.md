# Эмулятор командной оболочки

Этап 1: GUI REPL, заголовок с именем MyVFS, разделение ввода по пробелам.
`ls [args...]` и `cd [path]` — заглушки, выводящие имя команды и аргументы.
`exit` завершает работу. Лишние аргументы cd/exit и неизвестные команды — ошибки.
Приглашение: `localhost:~#`. Требуется Python 3.10+ с Tkinter.

Запуск в терминале ОС из корня проекта:

```text
python src/main.py
python -m unittest discover -s tests -v
python tests/check_style.py
```

Также можно использовать `run.bat` (Windows) или `sh run.sh` (Linux/macOS).

Интерактивная демонстрация: по очереди введите в окне эмулятора:

```text
ls
ls one two
cd
cd home
cd one two
unknown
exit now
exit
```

Дальнейшие этапы: конфигурация и CSV (2), JSON VFS (3), ls/cd/du/cal/history (4), mkdir/cp (5).
История старых коммитов не переписана; исправления записываются новыми scoped-коммитами.
