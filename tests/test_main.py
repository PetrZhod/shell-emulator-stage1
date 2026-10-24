"""Проверки VFS, команд и конфигурации этапов 3–5."""

import contextlib
import csv
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))
import main as app
from commands import Shell
from vfs import VirtualFileSystem


class ShellTests(unittest.TestCase):
    """Проверять команды на независимой временной VFS."""

    def setUp(self):
        """Создать копию образца и отдельный CSV-журнал."""
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name)
        self.path = self.folder / "vfs.json"
        example = Path(__file__).parents[1] / "examples/vfs.json"
        self.path.write_bytes(example.read_bytes())
        self.original = self.path.read_bytes()
        self.log = self.folder / "commands.csv"
        app.prepare_log(self.log)
        self.vfs = VirtualFileSystem(self.path)
        self.shell = Shell(self.vfs, self.log, app.log_command)

    def test_commands(self):
        """Проверить все доступные команды, режимы и неверные аргументы."""
        cases = [("ls", 0), ("cd", 0), ("cd one two", 1),
                 ("unknown", 127), ("exit now", 1), ("exit", 0)]
        if "du" in self.shell.handlers:
            cases += [("ls -al", 0), ("ls /hello.txt", 0), ("ls -x", 1),
                      ("cd /home/user/docs", 0), ("cd ..", 0), ("cd -", 0),
                      ("cd /hello.txt", 1), ("cd /missing", 1), ("cd", 0),
                      ("du", 0), ("du -s /", 0), ("du /missing", 1),
                      ("cal", 0), ("cal 2024", 0), ("cal 2 2024", 0),
                      ("cal 13 2024", 1), ("cal x", 1), ("cal 0", 1),
                      ("history", 0), ("history 1", 0), ("history 0", 0),
                      ("history -c", 0), ("history -1", 1)]
        if "mkdir" in self.shell.handlers:
            cases += [("mkdir /new", 0), ("mkdir /new", 1),
                      ("mkdir -p /new/a/b", 0), ("mkdir -p /new/a/b", 0),
                      ("mkdir /missing/child", 1), ("mkdir", 1),
                      ("cp /hello.txt /new/copy", 0),
                      ("cp /binary.bin /new/copy", 0),
                      ("cp -r /home /backup", 0), ("cp /home /x", 1),
                      ("cp -r /home /home/child", 1), ("cp", 1),
                      ("cp /hello.txt /hello.txt", 1), ("cp /missing /x", 1)]
        for line, status in cases:
            with self.subTest(line=line):
                self.assertEqual(self.shell.execute(line)[0], status)
        self.assertEqual(self.path.read_bytes(), self.original)

    def test_content_and_independence(self):
        """Проверить размеры декодированных данных и независимость копий."""
        if "du" in self.shell.handlers:
            self.assertEqual(self.shell.execute("du -s /")[1], "20\t/\n")
            self.assertNotIn(".hidden", self.shell.execute("ls")[1])
            self.assertIn(".hidden", self.shell.execute("ls -a")[1])
            self.assertIn("29", self.shell.execute("cal 2 2024")[1])
        if "cp" in self.shell.handlers:
            self.shell.execute("cp -r /home /backup")
            self.shell.execute("mkdir /backup/new")
            self.assertNotIn("new", self.vfs.resolve("/home")[1]["children"])
        self.assertEqual(self.path.read_bytes(), self.original)

    def test_csv(self):
        """Записать аргументы, пользователя и ошибку ровно в четыре поля."""
        with patch.object(app.getpass, "getuser", return_value="student"):
            self.shell.execute("unknown argument")
        with self.log.open(encoding="utf-8", newline="") as stream:
            row = list(csv.DictReader(stream))[0]
        self.assertEqual(set(row), set(app.LOG_FIELDS))
        self.assertEqual(row["username"], "student")
        self.assertEqual(json.loads(row["arguments"]), ["argument"])
        self.assertIn("not found", row["error"])
        app.prepare_log(self.log)
        self.assertEqual(self.shell.execute("  "), (0, "", "", False))

    def test_reset(self):
        """Очистить память и физический JSON; ошибочный reset их не меняет."""
        self.assertEqual(self.shell.execute("vfs-init extra")[0], 1)
        self.assertEqual(self.path.read_bytes(), self.original)
        with patch.object(Path, "write_text", side_effect=OSError("denied")):
            self.assertEqual(self.shell.execute("vfs-init")[0], 1)
        self.assertEqual(self.shell.execute("vfs-init")[0], 0)
        self.assertEqual(self.vfs.root["children"], {})
        self.assertEqual(VirtualFileSystem(self.path).root, self.vfs.root)

    def test_invalid_vfs(self):
        """Отклонить повреждённый JSON, неверные узлы и неверный base64."""
        cases = ("{", "{}", '{"name":"x","root":null}',
                 '{"name":"x","root":{"type":"file","data":"%%%"}}')
        for value in cases:
            self.path.write_text(value)
            with self.assertRaises(ValueError):
                VirtualFileSystem(self.path)

    def test_script_and_cli(self):
        """Проверить параметры, BOM, комментарии и номера строк скрипта."""
        script = self.folder / "my script.txt"
        script.write_text("# test\n\nls # inline\n", encoding="utf-8-sig")
        self.assertEqual(app.read_startup_script(script), [(3, "ls")])
        args = app.parse_arguments(["--vfs", str(self.path),
                                    "--log", str(self.log),
                                    "--script", str(script)])
        self.assertIn(str(script.resolve()), app.debug_parameters(args))
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                app.parse_arguments(["--log", "x", "--vfs", "x"])

    def test_demo_and_fixtures(self):
        """Выполнить демонстрацию и загрузить все три варианта VFS."""
        examples = Path(__file__).parents[1] / "examples"
        for name in ("minimal", "multiple", "deep"):
            VirtualFileSystem(examples / f"{name}.json")
        for _, line in app.read_startup_script(examples / "startup.txt"):
            result = self.shell.execute(line)
            self.assertIn(result[0], (0, 1, 127))
            if result[3]:
                break


if __name__ == "__main__":
    unittest.main()
