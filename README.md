Эмулятор командной оболочки. Вариант №10.

Этап 1. Графический REPL: разбор ввода на команду и аргументы, команды-заглушки и обработка ошибок.
Этап 2. Конфигурация через параметры командной строки, стартовый скрипт и CSV-лог.
Этап 3. Подключение VFS из JSON-файла и команда `vfs-init`.
Этап 4. Полноценные `ls`, `cd`, `du`, `cal`, `history`.
Этап 5. Команды изменения VFS: `mkdir`, `cp`.

Этап 1.

- Графический интерфейс реализован с помощью Tkinter.
- Заголовок окна содержит имя VFS `MyVFS`.
- Ввод разделяется на команду и аргументы по пробелам.
- `ls [args...]`, `cd [args...]` — заглушки, печатающие имя и аргументы.
- `exit` — завершение работы.
- Неизвестные команды и неверные аргументы выводят сообщение об ошибке.

Для проверки:

```text
localhost:~# ls one two
Command: ls
Arguments: ['one', 'two']
localhost:~# cd home
Command: cd
Arguments: ['home']
localhost:~# cd one two
cd: too many arguments
localhost:~# unknown
sh: unknown: not found
localhost:~# exit
exit
```

Сборка и запуск

Требуется Python 3.10+ с поддержкой Tkinter.

```bash
pip install -r requirements-dev.txt
python src/main.py
python -m pytest tests
```

На Windows программу также можно запустить файлом `run.bat`.
