"""Эмулятор оболочки. Вариант 10, этапы 3–5."""

import argparse
import csv
import getpass
import json
import sys
from pathlib import Path

from vfs import VirtualFileSystem
from commands import Shell

PROMPT = "localhost:~# "
LOG_FIELDS = ["command", "arguments", "username", "error"]


def parse_arguments(argv=None):
    """Прочитать параметры запуска относительно текущей папки."""
    parser = argparse.ArgumentParser(description="Shell Emulator")
    parser.add_argument("--vfs", type=Path, default=Path("examples/vfs.json"),
                        help="путь к JSON VFS")
    parser.add_argument("--log", type=Path, default=Path("logs/commands.csv"),
                        help="путь к CSV-логу")
    parser.add_argument("--script", type=Path, default=None,
                        help="путь к стартовому скрипту UTF-8")
    args = parser.parse_args(argv)
    if args.log.resolve() == args.vfs.resolve():
        parser.error("--log и --vfs должны указывать на разные файлы")
    if args.script is not None and args.log.resolve() == args.script.resolve():
        parser.error("--log и --script должны указывать на разные файлы")
    return args


def debug_parameters(args):
    """Показать все параметры при запуске в консоли и GUI."""
    script = "(не задан)"
    if args.script is not None:
        script = str(args.script.resolve())
    return (
        f"[config] VFS: {args.vfs.resolve()}\n"
        f"[config] CSV log: {args.log.resolve()}\n"
        f"[config] Startup script: {script}\n"
    )


def prepare_log(path):
    """Создать CSV с заголовком либо проверить существующий журнал."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size:
        with path.open("r", encoding="utf-8", newline="") as stream:
            if next(csv.reader(stream), None) != LOG_FIELDS:
                raise ValueError("CSV-файл имеет неподходящий заголовок")
    else:
        with path.open("w", encoding="utf-8", newline="") as stream:
            csv.writer(stream).writerow(LOG_FIELDS)


def log_command(path, command, arguments, error):
    """Добавить событие с пользователем и ошибкой в четыре поля CSV."""
    with Path(path).open("a", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=LOG_FIELDS)
        writer.writerow({
            "username": getpass.getuser(),
            "command": command,
            "arguments": json.dumps(arguments, ensure_ascii=False),
            "error": error,
        })


def read_startup_script(path):
    """Прочитать скрипт целиком; # начинает комментарий Python."""
    commands = []
    with Path(path).open("r", encoding="utf-8-sig") as stream:
        for number, line in enumerate(stream, start=1):
            command_line = line.split("#", 1)[0].strip()
            if command_line:
                commands.append((number, command_line))
    return commands


class ShellWindow:
    """Связать графический REPL, стартовый скрипт и команды."""

    def __init__(self, args, session):
        """Создать окно и виджеты без запуска цикла событий."""
        import tkinter as tk

        self.tk = tk
        self.args = args
        self.session = session
        self.last_status = 0
        self.root = tk.Tk()
        self.root.title(f"Shell Emulator — {session.vfs.name}")
        self.root.geometry("800x500")
        self.root.configure(bg="#1e1e1e")
        self.create_output()
        self.create_input()

    def create_output(self):
        """Создать защищённую от ручного редактирования область вывода."""
        tk = self.tk
        self.output = tk.Text(
            self.root, bg="#000000", fg="white",
            font=("Consolas", 12), state=tk.DISABLED,
        )
        self.output.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    def create_input(self):
        """Создать приглашение и поле ввода, связанное с Enter."""
        tk = self.tk
        frame = tk.Frame(self.root, bg="#000000")
        frame.pack(fill=tk.X, padx=10, pady=(0, 30))
        prompt = tk.Label(
            frame, text=PROMPT, bg="#1e1e1e", fg="#00ff00",
            font=("Consolas", 12),
        )
        prompt.pack(side=tk.LEFT)
        self.entry = tk.Entry(
            frame, bg="#2d2d2d", fg="white",
            insertbackground="white", font=("Consolas", 12),
        )
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.entry.focus_set()
        self.entry.bind("<Return>", self.process_input)

    def display(self, text):
        """Добавить текст в GUI и восстановить запрет редактирования."""
        tk = self.tk
        self.output.config(state=tk.NORMAL)
        self.output.insert(tk.END, text)
        self.output.see(tk.END)
        self.output.config(state=tk.DISABLED)

    def process_line(self, command_line, source="interactive", number=None):
        """Выполнить строку из GUI или скрипта и показать результат."""
        if not command_line.strip():
            return False
        self.display(f"{PROMPT}{command_line}\n")
        result = self.session.execute(command_line)
        self.last_status, text, error, should_exit = result
        self.display(text)
        if error:
            prefix = ""
            if number is not None:
                prefix = f"script: {source}:{number}: "
            self.display(prefix + error + "\n")
        if should_exit:
            self.entry.config(state=self.tk.DISABLED)
            self.root.after(100, self.root.destroy)
        return should_exit

    def process_input(self, event):
        """Получить строку из поля ввода при нажатии Enter."""
        command_line = self.entry.get()
        self.entry.delete(0, self.tk.END)
        self.process_line(command_line)
        return "break"

    def run_startup_script(self):
        """Продолжать после ошибок команд и останавливаться после exit."""
        path = self.args.script
        if path is None:
            return
        try:
            commands = read_startup_script(path)
        except (OSError, UnicodeError) as exc:
            self.last_status = 1
            self.display(f"script: cannot read {path}: {exc}\n")
            return
        for number, command_line in commands:
            if self.process_line(command_line, str(path), number):
                break

    def start(self, config_text):
        """Вывести настройки и запустить скрипт после создания GUI."""
        self.display(config_text)
        self.root.after(0, self.run_startup_script)
        self.root.mainloop()
        return self.last_status


def load_session(args):
    """Проверить VFS до GUI и сообщить об ошибке загрузки в консоль."""
    try:
        return Shell(VirtualFileSystem(args.vfs), args.log, log_command)
    except (OSError, ValueError, UnicodeError, RecursionError) as exc:
        print(f"vfs: cannot load {args.vfs}: {exc}", file=sys.stderr)
        return None


def main(argv=None):
    """Проверить конфигурацию и журнал, затем запустить GUI."""
    args = parse_arguments(argv)
    config_text = debug_parameters(args)
    print(config_text, end="")
    try:
        prepare_log(args.log)
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"log: cannot initialize {args.log}: {exc}", file=sys.stderr)
        return 1
    session = load_session(args)
    if session is None:
        return 1
    window = ShellWindow(args, session)
    return window.start(config_text)


if __name__ == "__main__":
    sys.exit(main())
