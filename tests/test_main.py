"""Тесты исходной реализации с подменой графических компонентов."""

import runpy
import sys
import types
import unittest
from pathlib import Path


class FakeWidget:
    """Минимальная подмена виджетов Tkinter для тестов."""

    def __init__(self, *args, **kwargs):
        """Создать виджет с пустыми вводом и выводом."""
        self.value = ""
        self.text = ""
        self.destroyed = False

    def pack(self, *args, **kwargs):
        """Имитировать размещение виджета."""

    def bind(self, *args, **kwargs):
        """Имитировать назначение обработчика."""

    def config(self, *args, **kwargs):
        """Имитировать изменение настроек."""

    def insert(self, *args):
        """Сохранить выведенный текст."""
        self.text += str(args[1])

    def delete(self, *args):
        """Очистить поле ввода."""
        self.value = ""

    def get(self):
        """Вернуть содержимое поля ввода."""
        return self.value

    def see(self, *args):
        """Имитировать прокрутку."""

    def title(self, *args):
        """Имитировать установку заголовка."""

    def geometry(self, *args):
        """Имитировать установку размера."""

    def after(self, delay, callback):
        """Сразу выполнить отложенное действие."""
        callback()

    def destroy(self):
        """Отметить окно как закрытое."""
        self.destroyed = True

    def mainloop(self):
        """Не запускать цикл GUI во время тестов."""


def load_program():
    """Загрузить исходную программу с подменённым Tkinter."""
    fake_tkinter = types.ModuleType("tkinter")
    for name in ("Tk", "Text", "Frame", "Label", "Entry"):
        setattr(fake_tkinter, name, FakeWidget)
    fake_tkinter.DISABLED = "disabled"
    fake_tkinter.NORMAL = "normal"
    fake_tkinter.BOTH = "both"
    fake_tkinter.X = "x"
    fake_tkinter.LEFT = "left"
    fake_tkinter.END = "end"
    sys.modules["tkinter"] = fake_tkinter
    source = Path(__file__).parents[1] / "src" / "main.py"
    return runpy.run_path(str(source))


class ShellEmulatorTests(unittest.TestCase):
    """Проверки команд исходной реализации."""

    def setUp(self):
        """Загружать чистый экземпляр программы для каждого теста."""
        self.program = load_program()
        self.entry = self.program["command_entry"]
        self.output = self.program["output"]

    def run_command(self, command):
        """Ввести команду и вернуть появившийся вывод."""
        before = len(self.output.text)
        self.entry.value = command
        self.program["process_input"](None)
        return self.output.text[before:]

    def test_ls(self):
        """Проверить заглушку ls."""
        result = self.run_command("ls one two")
        self.assertIn("Command: ls", result)
        self.assertIn("['one', 'two']", result)

    def test_cd_error(self):
        """Проверить ошибку лишних аргументов cd."""
        result = self.run_command("cd one two")
        self.assertIn("cd: too many arguments", result)

    def test_unknown_command(self):
        """Проверить сообщение о неизвестной команде."""
        result = self.run_command("unknown")
        self.assertIn("sh: unknown: not found", result)

    def test_exit(self):
        """Проверить закрытие окна командой exit."""
        self.run_command("exit")
        self.assertTrue(self.program["root"].destroyed)


if __name__ == "__main__":
    unittest.main()
