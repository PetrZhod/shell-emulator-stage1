"""Этапы 1–2: команды, конфигурация, CSV и GUI с подменой Tkinter."""

import contextlib
import csv
import importlib.util
import io
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

SOURCE = Path(__file__).parents[1] / "src" / "main.py"
spec = importlib.util.spec_from_file_location("shell_main", SOURCE)
shell = importlib.util.module_from_spec(spec)
spec.loader.exec_module(shell)


class FakeWidget:
    """Тестовые виджеты."""
    def __init__(self, *args, **kwargs):
        """Создать пустой виджет с очередью событий."""
        self.value = ""
        self.text = ""
        self.destroyed = False
        self.callbacks = []
        self.bindings = {}
        self.options = dict(kwargs)
        self.title_text = ""

    def pack(self, *args, **kwargs):
        """Имитировать размещение виджета без GUI."""
        pass

    def focus_set(self):
        """Имитировать установку фокуса ввода."""
        pass

    def bind(self, key, callback):
        """Сохранить обработчик события клавиатуры."""
        self.bindings[key] = callback

    def config(self, **kwargs):
        """Обновить параметры тестового виджета."""
        self.options.update(kwargs)

    configure = config

    def insert(self, index, text):
        """Добавить текст в тестовую область вывода."""
        self.text += str(text)

    def delete(self, *args):
        """Очистить тестовое поле ввода."""
        self.value = ""

    def get(self):
        """Вернуть текст из тестового поля ввода."""
        return self.value

    def see(self, *args):
        """Имитировать прокрутку области вывода."""
        pass

    def title(self, text):
        """Сохранить заголовок тестового окна."""
        self.title_text = text

    def geometry(self, *args):
        """Имитировать установку размера окна."""
        pass

    def after(self, delay, callback):
        """Добавить действие в очередь событий."""
        self.callbacks.append(callback)

    def destroy(self):
        """Отметить тестовое окно как закрытое."""
        self.destroyed = True

    def mainloop(self):
        """Обработать очередь до закрытия тестового окна."""
        while self.callbacks and not self.destroyed:
            self.callbacks.pop(0)()


def fake_tkinter():
    """Создать подмену модуля Tkinter для тестов."""
    module = types.ModuleType("tkinter")
    module.widgets = []

    def create(*args, **kwargs):
        """Создать и зарегистрировать тестовый виджет."""
        widget = FakeWidget(*args, **kwargs)
        module.widgets.append(widget)
        return widget

    for name in ("Tk", "Text", "Frame", "Label", "Entry"):
        setattr(module, name, create)
    for name in ("DISABLED", "NORMAL", "BOTH", "X", "LEFT", "END"):
        setattr(module, name, name.lower())
    return module


class ShellTests(unittest.TestCase):
    """Проверки команд и конфигурации."""
    def setUp(self):
        """Создать отдельную временную папку и журнал для теста."""
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.log = self.folder / "logs" / "commands.csv"
        shell.prepare_log(self.log)

    def rows(self, path=None):
        """Прочитать CSV-журнал как список словарей."""
        with (path or self.log).open(encoding="utf-8", newline="") as stream:
            return list(csv.DictReader(stream))

    def command(self, line):
        """Выполнить команду с журналом текущего теста."""
        return shell.execute_command(line, self.log)

    def run_gui(self, script=None):
        """Запустить приложение с подменой Tkinter и вывода."""
        fake = fake_tkinter()
        argv = [
            "--vfs", str(self.folder / "MyVFS.json"),
            "--log", str(self.log),
        ]
        if script is not None:
            argv += ["--script", str(script)]
        console = io.StringIO()
        with patch.dict(sys.modules, {"tkinter": fake}):
            with contextlib.redirect_stdout(console):
                status = shell.main(argv)
        return status, fake, console.getvalue()

    def test_ls(self):
        """Проверить вывод заглушки ls с аргументами."""
        status, text, error, exiting = self.command("ls one two")
        self.assertEqual((status, error, exiting), (0, "", False))
        self.assertIn("Command: ls\nArguments: ['one', 'two']", text)

    def test_parser_spaces(self):
        """Проверить разделение по пробелам и табуляции."""
        self.command("  ls   one\t two  ")
        arguments = json.loads(self.rows()[0]["arguments"])
        self.assertEqual(arguments, ["one", "two"])

    def test_cd_without_arguments(self):
        """Проверить cd без аргументов."""
        self.assertIn("Arguments: []", self.command("cd")[1])

    def test_cd_with_argument(self):
        """Проверить cd с одним аргументом."""
        self.assertIn("['home']", self.command("cd home")[1])

    def test_cd_error(self):
        """Проверить ошибку лишних аргументов cd."""
        self.assertEqual(self.command("cd one two")[0:3],
                         (1, "", "cd: too many arguments"))

    def test_unknown(self):
        """Проверить сообщение о неизвестной команде."""
        self.assertEqual(self.command("unknown")[0:3],
                         (127, "", "sh: unknown: not found"))

    def test_exit(self):
        """Проверить результат exit и запись в журнале."""
        self.assertEqual(self.command("exit"), (0, "exit\n", "", True))
        self.assertEqual(self.rows()[0]["command"], "exit")

    def test_exit_error(self):
        """Проверить отказ завершения при аргументах exit."""
        self.assertEqual(self.command("exit now"),
                         (1, "", "exit: too many arguments", False))

    def test_empty_input_not_logged(self):
        """Проверить отсутствие записи для пустого ввода."""
        self.assertEqual(self.command("   "), (0, "", "", False))
        self.assertEqual(self.rows(), [])

    def test_csv_contains_only_required_fields(self):
        """Проверить четыре поля журнала, пользователя и ошибку."""
        with patch.object(shell.getpass, "getuser", return_value="student"):
            shell.execute_command("cd one two", self.log)
        row = self.rows()[0]
        self.assertEqual(row["username"], "student")
        self.assertEqual(row["error"], "cd: too many arguments")
        self.assertEqual(row["command"], "cd")
        self.assertEqual(json.loads(row["arguments"]), ["one", "two"])
        fields = {"command", "arguments", "username", "error"}
        self.assertEqual(set(row), fields)

    def test_csv_unicode_commas_and_quotes(self):
        """Проверить кириллицу, запятые и кавычки в CSV."""
        self.command('ls папка,файл "test"')
        self.assertEqual(json.loads(self.rows()[0]["arguments"]),
                         ["папка,файл", '"test"'])

    def test_csv_append_and_single_header(self):
        """Проверить добавление записей без повторного заголовка."""
        self.command("ls")
        shell.prepare_log(self.log)
        self.command("cd home")
        self.assertEqual(len(self.rows()), 2)
        self.assertTrue(all(row["error"] == "" for row in self.rows()))
        content = self.log.read_text(encoding="utf-8")
        self.assertEqual(content.count("command,arguments,username,error"), 1)

    def test_existing_non_csv_not_overwritten(self):
        """Проверить сохранность файла с неверным заголовком."""
        self.log.write_text("important data", encoding="utf-8")
        with self.assertRaises(ValueError):
            shell.prepare_log(self.log)
        self.assertEqual(self.log.read_text(), "important data")

    def test_log_directory_error(self):
        """Проверить ошибку при выборе папки вместо CSV."""
        with self.assertRaises(OSError):
            shell.prepare_log(self.folder)

    def test_logging_failure_reported(self):
        """Проверить сообщение об ошибке записи журнала."""
        with patch.object(shell, "log_command", side_effect=OSError("denied")):
            status, text, error, exiting = self.command("ls")
        self.assertEqual(status, 1)
        self.assertIn("log: denied", error)
        self.assertFalse(exiting)

    def test_cli_defaults(self):
        """Проверить значения параметров по умолчанию."""
        args = shell.parse_arguments([])
        self.assertEqual(args.vfs, Path("vfs.json"))
        self.assertEqual(args.log, Path("logs/commands.csv"))
        self.assertIsNone(args.script)

    def test_cli_paths_with_spaces(self):
        """Проверить параметры запуска с пробелами в путях."""
        args = shell.parse_arguments([
            "--vfs", "my vfs.json",
            "--log", "my log.csv",
            "--script", "my script.txt",
        ])
        self.assertEqual(args.script, Path("my script.txt"))
        self.assertIn(str(args.vfs.resolve()), shell.debug_parameters(args))

    def test_cli_invalid_options(self):
        """Проверить отклонение неверных параметров запуска."""
        for argv in (["--script"], ["--unknown"], ["--log", "a", "--vfs", "a"],
                     ["--log", "a", "--script", "a"]):
            with self.subTest(argv=argv):
                self.check_invalid_arguments(argv)

    def check_invalid_arguments(self, argv):
        """Проверить код завершения для ошибочных параметров."""
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as caught:
                shell.parse_arguments(argv)
            self.assertEqual(caught.exception.code, 2)

    def test_script_comments_bom_and_line_numbers(self):
        """Проверить комментарии, UTF-8 BOM и номера строк."""
        script = self.folder / "startup.txt"
        script.write_text(
            "# comment\n\nls one # comment\ncd home\n",
            encoding="utf-8-sig",
        )
        expected = [(3, "ls one"), (4, "cd home")]
        self.assertEqual(shell.read_startup_script(script), expected)

    def test_script_invalid_utf8(self):
        """Проверить отказ чтения файла с неверной кодировкой."""
        script = self.folder / "bad.txt"
        script.write_bytes(b"ls\n\xff")
        with self.assertRaises(UnicodeError):
            shell.read_startup_script(script)

    def test_gui_config_and_interactive_commands(self):
        """Проверить настройки, ввод команд и закрытие GUI."""
        status, fake, console = self.run_gui()
        root, output, frame, prompt, entry = fake.widgets
        self.assertIn("MyVFS.json", root.title_text)
        self.assertIn("[config] Startup script: (не задан)", output.text)
        self.assertIn("[config] CSV log:", console)
        commands = [
            "ls", "cd home", "cd one two", "unknown", "exit now", "",
        ]
        for command in commands:
            entry.value = command
            self.assertEqual(entry.bindings["<Return>"](None), "break")
            self.assertEqual(entry.value, "")
        self.assertEqual(len(self.rows()), 5)
        self.assertEqual(output.options["state"], "disabled")
        entry.value = "exit"
        entry.bindings["<Return>"](None)
        root.mainloop()
        self.assertTrue(root.destroyed)

    def test_gui_script_errors_continue_and_exit_stops(self):
        """Проверить продолжение после ошибок и остановку по exit."""
        script = self.folder / "startup.txt"
        script.write_text(
            "# comment\nunknown\ncd one two\n"
            "exit now\nls ok\nexit\nls no\n",
            encoding="utf-8",
        )
        status, fake, _ = self.run_gui(script)
        output = fake.widgets[1].text
        self.assertIn("localhost:~# ls ok", output)
        self.assertIn(f"script: {script}:2:", output)
        self.assertIn("Command: ls", output)
        self.assertNotIn("ls no", output)
        self.assertTrue(fake.widgets[0].destroyed)
        self.assertEqual(status, 0)
        self.assertEqual([r["command"] for r in self.rows()],
                         ["unknown", "cd", "exit", "ls", "exit"])

    def test_gui_missing_script(self):
        """Проверить сообщение об отсутствующем скрипте."""
        status, fake, _ = self.run_gui(self.folder / "missing.txt")
        self.assertEqual(status, 1)
        self.assertIn("script: cannot read", fake.widgets[1].text)
        self.assertFalse(fake.widgets[0].destroyed)
        self.assertEqual(self.rows(), [])

    def test_gui_invalid_encoding_executes_nothing(self):
        """Проверить отсутствие исполнения при ошибке кодировки."""
        script = self.folder / "bad.txt"
        script.write_bytes(b"ls\n\xff")
        status, fake, _ = self.run_gui(script)
        self.assertEqual(status, 1)
        self.assertIn("script: cannot read", fake.widgets[1].text)
        self.assertEqual(self.rows(), [])

    def test_main_invalid_log_exits_before_gui(self):
        """Проверить отказ запуска GUI при ошибке журнала."""
        with contextlib.redirect_stdout(io.StringIO()):
            with contextlib.redirect_stderr(io.StringIO()):
                status = shell.main(["--log", str(self.folder)])
        self.assertEqual(status, 1)

    def test_vfs_file_is_not_modified(self):
        """Проверить неизменность исходного файла VFS."""
        vfs = self.folder / "MyVFS.json"
        vfs.write_bytes(b'{"unchanged":true}')
        self.run_gui()
        self.assertEqual(vfs.read_bytes(), b'{"unchanged":true}')


if __name__ == "__main__":
    unittest.main()
