"""Эмулятор оболочки. Вариант 10, этап 2: конфигурация и CSV-лог."""

import argparse
import csv
import getpass
import json
import sys
from pathlib import Path


PROMPT = "localhost:~# "
LOG_FIELDS = ["command", "arguments", "username", "error"]


def parse_arguments(argv=None):
    """Прочитать параметры запуска; пути разрешаются относительно текущей папки."""
    parser = argparse.ArgumentParser(description="Shell Emulator — этап 2")
    parser.add_argument("--vfs", type=Path, default=Path("vfs.json"),
                        help="путь к VFS (загрузка появится на этапе 3)")
    parser.add_argument("--log", type=Path, default=Path("logs/commands.csv"),
                        help="путь к CSV-логу")
    parser.add_argument("--script", type=Path, default=None,
                        help="путь к стартовому скрипту UTF-8")
    args = parser.parse_args(argv)
    # Не позволяем случайно записать лог поверх VFS или стартового скрипта.
    if args.log.resolve() == args.vfs.resolve():
        parser.error("--log и --vfs должны указывать на разные файлы")
    if args.script is not None and args.log.resolve() == args.script.resolve():
        parser.error("--log и --script должны указывать на разные файлы")
    return args


def debug_parameters(args):
    """Показать все параметры при запуске: в консоли и в графическом окне."""
    script = str(args.script.resolve()) if args.script is not None else "(не задан)"
    return (
        f"[config] VFS: {args.vfs.resolve()}\n"
        f"[config] CSV log: {args.log.resolve()}\n"
        f"[config] Startup script: {script}\n"
    )


def prepare_log(path):
    """Создать CSV с заголовком либо проверить формат существующего лога."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size > 0:
        with path.open("r", encoding="utf-8", newline="") as stream:
            if next(csv.reader(stream), None) != LOG_FIELDS:
                raise ValueError("CSV-файл имеет неподходящий заголовок")
    else:
        with path.open("w", encoding="utf-8", newline="") as stream:
            csv.writer(stream).writerow(LOG_FIELDS)


def log_command(path, command, arguments, error):
    """Добавить событие, не удаляя предыдущие записи."""
    with Path(path).open("a", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=LOG_FIELDS)
        writer.writerow({
            "username": getpass.getuser(),
            "command": command,
            "arguments": json.dumps(arguments, ensure_ascii=False),
            "error": error,
        })


def execute_command(command_line, log_path):
    """Разобрать команду, выполнить заглушку и вернуть статус, текст, ошибку, exit."""
    parts = command_line.split()
    if not parts:
        return 0, "", "", False
    command = parts[0]
    arguments = parts[1:]
    status, text, error, should_exit = 0, "", "", False

    if command == "ls":
        text = f"Command: ls\nArguments: {arguments}\n"
    elif command == "cd":
        if len(arguments) > 1:
            status, error = 1, "cd: too many arguments"
        else:
            text = f"Command: cd\nArguments: {arguments}\n"
    elif command == "exit":
        if arguments:
            status, error = 1, "exit: too many arguments"
        else:
            text, should_exit = "exit\n", True
    else:
        status, error = 127, f"sh: {command}: not found"

    try:
        log_command(log_path, command, arguments, error)
    except (OSError, UnicodeError, ValueError) as exc:
        # Ошибка журнала должна быть видна, а не приводить к падению GUI.
        error = (error + "\n" if error else "") + f"log: {exc}"
        status = 1
    return status, text, error, should_exit


def read_startup_script(path):
    """Прочитать скрипт целиком до исполнения; # начинает комментарий."""
    commands = []
    with Path(path).open("r", encoding="utf-8-sig") as stream:
        for number, line in enumerate(stream, start=1):
            command_line = line.split("#", 1)[0].strip()
            if command_line:
                commands.append((number, command_line))
    return commands


def main(argv=None):
    """Настроить эмулятор и запустить графический REPL."""
    args = parse_arguments(argv)
    config_text = debug_parameters(args)
    print(config_text, end="")
    try:
        prepare_log(args.log)
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"log: cannot initialize {args.log}: {exc}", file=sys.stderr)
        return 1

    # Импорт внутри main позволяет тестировать парсер и команды без GUI.
    import tkinter as tk

    root = tk.Tk()
    root.title(f"Shell Emulator — {args.vfs.name}")
    root.geometry("800x500")
    root.configure(bg="#1e1e1e")

    output = tk.Text(root, bg="#000000", fg="white",
                     font=("Consolas", 12), state=tk.DISABLED)
    output.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    input_frame = tk.Frame(root, bg="#000000")
    input_frame.pack(fill=tk.X, padx=10, pady=(0, 30))
    prompt = tk.Label(input_frame, text=PROMPT, bg="#1e1e1e",
                      fg="#00ff00", font=("Consolas", 12))
    prompt.pack(side=tk.LEFT)
    command_entry = tk.Entry(input_frame, bg="#2d2d2d", fg="white",
                             insertbackground="white", font=("Consolas", 12))
    command_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
    command_entry.focus_set()
    last_status = 0

    def process_line(command_line, source="interactive", line_number=None):
        """Один обработчик для GUI и стартового скрипта."""
        nonlocal last_status
        if not command_line.strip():
            return False
        output.config(state=tk.NORMAL)
        output.insert(tk.END, f"{PROMPT}{command_line}\n")
        last_status, text, error, should_exit = execute_command(
            command_line, args.log
        )
        output.insert(tk.END, text)
        if error:
            if line_number is not None:
                output.insert(tk.END, f"script: {source}:{line_number}: ")
            output.insert(tk.END, error + "\n")
        output.see(tk.END)
        output.config(state=tk.DISABLED)
        if should_exit:
            command_entry.config(state=tk.DISABLED)
            root.after(100, root.destroy)
        return should_exit

    def process_input(event):
        """Получить строку при нажатии Enter."""
        command_line = command_entry.get()
        command_entry.delete(0, tk.END)
        process_line(command_line)
        return "break"

    def run_startup_script():
        """Ошибка команды не останавливает скрипт; успешный exit останавливает."""
        nonlocal last_status
        if args.script is None:
            return
        try:
            commands = read_startup_script(args.script)
        except (OSError, UnicodeError) as exc:
            last_status = 1
            output.config(state=tk.NORMAL)
            output.insert(tk.END, f"script: cannot read {args.script}: {exc}\n")
            output.see(tk.END)
            output.config(state=tk.DISABLED)
            return
        for number, command_line in commands:
            if process_line(command_line, str(args.script), number):
                break

    output.config(state=tk.NORMAL)
    output.insert(tk.END, config_text)
    output.config(state=tk.DISABLED)
    command_entry.bind("<Return>", process_input)
    # Запуск после создания GUI: ввод и вывод скрипта видны в том же окне.
    root.after(0, run_startup_script)
    root.mainloop()
    return last_status


if __name__ == "__main__":
    sys.exit(main())
