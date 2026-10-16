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
    def __init__(self, *args, **kwargs):
        self.value = ""
        self.text = ""
        self.destroyed = False
        self.callbacks = []
        self.bindings = {}
        self.options = dict(kwargs)
        self.title_text = ""

    def pack(self, *args, **kwargs):
        pass

    def focus_set(self):
        pass

    def bind(self, key, callback):
        self.bindings[key] = callback

    def config(self, **kwargs):
        self.options.update(kwargs)

    configure = config

    def insert(self, index, text):
        self.text += str(text)

    def delete(self, *args):
        self.value = ""

    def get(self):
        return self.value

    def see(self, *args):
        pass

    def title(self, text):
        self.title_text = text

    def geometry(self, *args):
        pass

    def after(self, delay, callback):
        self.callbacks.append(callback)

    def destroy(self):
        self.destroyed = True

    def mainloop(self):
        while self.callbacks and not self.destroyed:
            self.callbacks.pop(0)()


def fake_tkinter():
    module = types.ModuleType("tkinter")
    module.widgets = []

    def create(*args, **kwargs):
        widget = FakeWidget(*args, **kwargs)
        module.widgets.append(widget)
        return widget

    for name in ("Tk", "Text", "Frame", "Label", "Entry"):
        setattr(module, name, create)
    for name in ("DISABLED", "NORMAL", "BOTH", "X", "LEFT", "END"):
        setattr(module, name, name.lower())
    return module


class ShellTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.log = self.folder / "logs" / "commands.csv"
        shell.prepare_log(self.log)

    def rows(self, path=None):
        with (path or self.log).open(encoding="utf-8", newline="") as stream:
            return list(csv.DictReader(stream))

    def command(self, line):
        return shell.execute_command(line, self.log)

    def run_gui(self, script=None):
        fake = fake_tkinter()
        argv = ["--vfs", str(self.folder / "MyVFS.json"), "--log", str(self.log)]
        if script is not None:
            argv += ["--script", str(script)]
        console = io.StringIO()
        with patch.dict(sys.modules, {"tkinter": fake}), contextlib.redirect_stdout(console):
            status = shell.main(argv)
        return status, fake, console.getvalue()

    def test_ls(self):
        status, text, error, exiting = self.command("ls one two")
        self.assertEqual((status, error, exiting), (0, "", False))
        self.assertIn("Command: ls\nArguments: ['one', 'two']", text)

    def test_parser_spaces(self):
        self.command("  ls   one\t two  ")
        self.assertEqual(json.loads(self.rows()[0]["arguments"]), ["one", "two"])

    def test_cd_without_arguments(self):
        self.assertIn("Arguments: []", self.command("cd")[1])

    def test_cd_with_argument(self):
        self.assertIn("['home']", self.command("cd home")[1])

    def test_cd_error(self):
        self.assertEqual(self.command("cd one two")[0:3],
                         (1, "", "cd: too many arguments"))

    def test_unknown(self):
        self.assertEqual(self.command("unknown")[0:3],
                         (127, "", "sh: unknown: not found"))

    def test_exit(self):
        self.assertEqual(self.command("exit"), (0, "exit\n", "", True))
        self.assertEqual(self.rows()[0]["command"], "exit")

    def test_exit_error(self):
        self.assertEqual(self.command("exit now"),
                         (1, "", "exit: too many arguments", False))

    def test_empty_input_not_logged(self):
        self.assertEqual(self.command("   "), (0, "", "", False))
        self.assertEqual(self.rows(), [])

    def test_csv_records_username_error_and_source(self):
        with patch.object(shell.getpass, "getuser", return_value="student"):
            shell.execute_command("cd one two", self.log, "demo.txt", 8)
        row = self.rows()[0]
        self.assertEqual(row["username"], "student")
        self.assertEqual(row["error"], "cd: too many arguments")
        self.assertEqual(row["status"], "1")
        self.assertEqual((row["source"], row["line_number"]), ("demo.txt", "8"))
        self.assertTrue(row["timestamp"])

    def test_csv_unicode_commas_and_quotes(self):
        self.command('ls папка,файл "test"')
        self.assertEqual(json.loads(self.rows()[0]["arguments"]),
                         ["папка,файл", '"test"'])

    def test_csv_append_and_single_header(self):
        self.command("ls")
        shell.prepare_log(self.log)
        self.command("cd home")
        self.assertEqual(len(self.rows()), 2)
        self.assertEqual(self.log.read_text().count("timestamp,username"), 1)

    def test_existing_non_csv_not_overwritten(self):
        self.log.write_text("important data", encoding="utf-8")
        with self.assertRaises(ValueError):
            shell.prepare_log(self.log)
        self.assertEqual(self.log.read_text(), "important data")

    def test_log_directory_error(self):
        with self.assertRaises(OSError):
            shell.prepare_log(self.folder)

    def test_logging_failure_reported(self):
        with patch.object(shell, "log_command", side_effect=OSError("denied")):
            status, text, error, exiting = self.command("ls")
        self.assertEqual(status, 1)
        self.assertIn("log: denied", error)
        self.assertFalse(exiting)

    def test_cli_defaults(self):
        args = shell.parse_arguments([])
        self.assertEqual(args.vfs, Path("vfs.json"))
        self.assertEqual(args.log, Path("logs/commands.csv"))
        self.assertIsNone(args.script)

    def test_cli_paths_with_spaces(self):
        args = shell.parse_arguments(["--vfs", "my vfs.json", "--log", "my log.csv",
                                      "--script", "my script.txt"])
        self.assertEqual(args.script, Path("my script.txt"))
        self.assertIn(str(args.vfs.resolve()), shell.debug_parameters(args))

    def test_cli_invalid_options(self):
        for argv in (["--script"], ["--unknown"], ["--log", "a", "--vfs", "a"],
                     ["--log", "a", "--script", "a"]):
            with self.subTest(argv=argv), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as caught:
                    shell.parse_arguments(argv)
                self.assertEqual(caught.exception.code, 2)

    def test_script_comments_bom_and_line_numbers(self):
        script = self.folder / "startup.txt"
        script.write_text("# comment\n\nls one # comment\ncd home\n", encoding="utf-8-sig")
        self.assertEqual(shell.read_startup_script(script), [(3, "ls one"), (4, "cd home")])

    def test_script_invalid_utf8(self):
        script = self.folder / "bad.txt"
        script.write_bytes(b"ls\n\xff")
        with self.assertRaises(UnicodeError):
            shell.read_startup_script(script)

    def test_gui_config_and_interactive_commands(self):
        status, fake, console = self.run_gui()
        root, output, frame, prompt, entry = fake.widgets
        self.assertIn("MyVFS.json", root.title_text)
        self.assertIn("[config] Startup script: (не задан)", output.text)
        self.assertIn("[config] CSV log:", console)
        for command in ["ls", "cd home", "cd one two", "unknown", "exit now", ""]:
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
        script = self.folder / "startup.txt"
        script.write_text("# comment\nunknown\ncd one two\nexit now\nls ok\nexit\nls no\n")
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
        status, fake, _ = self.run_gui(self.folder / "missing.txt")
        self.assertEqual(status, 1)
        self.assertIn("script: cannot read", fake.widgets[1].text)
        self.assertFalse(fake.widgets[0].destroyed)
        self.assertEqual(self.rows(), [])

    def test_gui_invalid_encoding_executes_nothing(self):
        script = self.folder / "bad.txt"
        script.write_bytes(b"ls\n\xff")
        status, fake, _ = self.run_gui(script)
        self.assertEqual(status, 1)
        self.assertIn("script: cannot read", fake.widgets[1].text)
        self.assertEqual(self.rows(), [])

    def test_main_invalid_log_exits_before_gui(self):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            status = shell.main(["--log", str(self.folder)])
        self.assertEqual(status, 1)

    def test_vfs_file_is_not_modified(self):
        vfs = self.folder / "MyVFS.json"
        vfs.write_bytes(b'{"unchanged":true}')
        self.run_gui()
        self.assertEqual(vfs.read_bytes(), b'{"unchanged":true}')


if __name__ == "__main__":
    unittest.main()
