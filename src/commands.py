"""Команды этапа 3: заглушки ls/cd, exit и очистка VFS."""

UNKNOWN_COMMAND = 127
MAX_SINGLE_PATH = 1


def one_path(paths, default="."):
    """Принять не более одного пути либо значение по умолчанию."""
    if len(paths) > MAX_SINGLE_PATH:
        raise ValueError("too many arguments")
    return paths[0] if paths else default


class Shell:
    """Хранить VFS и журнал одной сессии независимо от GUI."""

    def __init__(self, vfs, log_path, logger):
        """Сохранить VFS, путь журнала и пустую историю команд."""
        self.vfs = vfs
        self.log_path = log_path
        self.logger = logger
        self.history = []
        self.handlers = {
            "ls": self.ls, "cd": self.cd, "exit": self.exit,
            "vfs-init": self.vfs_init,
        }

    def execute(self, command_line):
        """Вернуть статус, вывод, ошибку и признак завершения."""
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
        """Преобразовать ошибки команд в сообщения для GUI и журнала."""
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
        """Очистить память и физический JSON командой без аргументов."""
        if arguments:
            raise ValueError("too many arguments")
        self.vfs.reset()
        return "VFS initialized\n"

    def ls(self, arguments):
        """Вывести имя и аргументы заглушки ls до этапа 4."""
        return f"Command: ls\nArguments: {arguments}\n"

    def cd(self, arguments):
        """Проверить число аргументов заглушки cd до этапа 4."""
        one_path(arguments)
        return f"Command: cd\nArguments: {arguments}\n"
