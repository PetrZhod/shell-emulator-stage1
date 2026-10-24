"""Команды UNIX-подобного эмулятора и единая запись событий в CSV."""

import calendar
from datetime import date

from vfs import disk_usage, file_size

UNKNOWN_COMMAND = 127
MAX_SINGLE_PATH = 1
MAX_CAL_ARGUMENTS = 2
MIN_YEAR = 1
MAX_YEAR = 9999
MIN_MONTH = 1
MAX_MONTH = 12
MIN_HISTORY_COUNT = 0


def options(arguments, allowed):
    """Разделить короткие флаги и пути; -- завершает список флагов."""
    flags, paths = set(), []
    parsing = True
    for argument in arguments:
        if parsing and argument == "--":
            parsing = False
        elif parsing and argument.startswith("-") and argument != "-":
            for flag in argument[1:]:
                if flag not in allowed:
                    raise ValueError(f"invalid option: -{flag}")
                flags.add(flag)
        else:
            paths.append(argument)
    return flags, paths


def one_path(paths, default="."):
    """Принять не более одного пути либо значение по умолчанию."""
    if len(paths) > MAX_SINGLE_PATH:
        raise ValueError("too many arguments")
    return paths[0] if paths else default


class Shell:
    """Хранить VFS и историю одной сессии независимо от GUI."""

    def __init__(self, vfs, log_path, logger):
        """Сохранить VFS, путь журнала и пустую историю команд."""
        self.vfs = vfs
        self.log_path = log_path
        self.logger = logger
        self.history = []
        self.handlers = {
            "ls": self.ls, "cd": self.cd, "exit": self.exit,
            "vfs-init": self.vfs_init,
            "du": self.du, "cal": self.cal,
            "history": self.show_history,
        }

    def execute(self, command_line):
        """Обработать команду и вернуть статус, вывод, ошибку и exit."""
        parts = command_line.split()
        if not parts:
            return 0, "", "", False
        command, arguments = parts[0], parts[1:]
        self.history.append(command_line.strip())
        status, text, error, exiting = self.dispatch(command, arguments)
        try:
            self.logger(self.log_path, command, arguments, error)
        except (OSError, UnicodeError, ValueError) as exc:
            error = (error + "\n" if error else "") + f"log: {exc}"
            status = 1
        return status, text, error, exiting

    def dispatch(self, command, arguments):
        """Найти обработчик и преобразовать ожидаемые ошибки в сообщения."""
        if command not in self.handlers:
            return UNKNOWN_COMMAND, "", f"sh: {command}: not found", False
        try:
            text = self.handlers[command](arguments)
            return 0, text, "", command == "exit"
        except (OSError, ValueError) as exc:
            return 1, "", f"{command}: {exc}", False

    def exit(self, arguments):
        """Завершить сеанс только при отсутствии аргументов."""
        if arguments:
            raise ValueError("too many arguments")
        return "exit\n"

    def vfs_init(self, arguments):
        """Заменить текущую и физическую VFS пустой VFS по умолчанию."""
        if arguments:
            raise ValueError("too many arguments")
        self.vfs.reset()
        return "VFS initialized\n"

    def ls(self, arguments):
        """Показать каталог или файл; -a включает скрытые, -l размер."""
        flags, paths = options(arguments, "al")
        path = one_path(paths)
        _, node = self.vfs.resolve(path)
        if node["type"] == "file":
            return self.list_item(path, node, flags) + "\n"
        lines = []
        for name, child in sorted(node["children"].items()):
            if name.startswith(".") and "a" not in flags:
                continue
            lines.append(self.list_item(name, child, flags))
        return "\n".join(lines) + ("\n" if lines else "")

    def list_item(self, name, node, flags):
        """Сформировать короткую либо подробную строку ls."""
        if "l" not in flags:
            return name
        if node["type"] == "directory":
            return f"d 0 {name}"
        return f"- {file_size(node)} {name}"

    def cd(self, arguments):
        """Перейти по пути; без аргументов в корень, - в прошлый каталог."""
        path = one_path(arguments, "/")
        self.vfs.change_directory(path)
        if path == "-":
            return "/" + "/".join(self.vfs.cwd) + "\n"
        return ""

    def du(self, arguments):
        """Показать размер дерева в байтах; -s выводит лишь итог."""
        flags, paths = options(arguments, "s")
        path = one_path(paths)
        _, node = self.vfs.resolve(path)
        _, lines = disk_usage(node, path, "s" in flags)
        return "\n".join(lines) + "\n"

    def cal(self, arguments):
        """Вывести текущий месяц, целый год либо месяц указанного года."""
        if len(arguments) > MAX_CAL_ARGUMENTS:
            raise ValueError("usage: cal [year | month year]")
        today = date.today()
        year, month = today.year, today.month
        if arguments:
            year = int(arguments[-1])
        if len(arguments) == MAX_CAL_ARGUMENTS:
            month = int(arguments[0])
        if not MIN_YEAR <= year <= MAX_YEAR:
            raise ValueError("year must be in 1..9999")
        if not MIN_MONTH <= month <= MAX_MONTH:
            raise ValueError("month must be in 1..12")
        printer = calendar.TextCalendar(firstweekday=calendar.MONDAY)
        if len(arguments) == MAX_SINGLE_PATH:
            return printer.formatyear(year)
        return printer.formatmonth(year, month)

    def show_history(self, arguments):
        """Показать историю, последние N записей либо очистить её через -c."""
        value = one_path(arguments, "")
        if value == "-c":
            self.history.clear()
            return ""
        start = 0
        if value:
            count = int(value)
            if count < MIN_HISTORY_COUNT:
                raise ValueError("count must be nonnegative")
            start = max(0, len(self.history) - count)
        lines = [f"{index + 1}  {line}"
                 for index, line in enumerate(self.history) if index >= start]
        return "\n".join(lines) + ("\n" if lines else "")
