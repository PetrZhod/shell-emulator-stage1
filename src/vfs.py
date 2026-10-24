"""JSON VFS: дерево каталогов и файлы base64, операции в памяти."""

import base64
import binascii
import copy
import json
from pathlib import Path


def directory():
    """Создать независимый пустой каталог."""
    return {"type": "directory", "children": {}}


def validate_node(node):
    """Проверить тип узла, имена детей и кодировку двоичных данных."""
    if not isinstance(node, dict):
        raise ValueError("VFS: node must be an object")
    kind = node.get("type")
    if kind == "file":
        if set(node) != {"type", "data"}:
            raise ValueError("VFS: file requires type and data")
        if not isinstance(node["data"], str):
            raise ValueError("VFS: data must be base64 text")
        try:
            base64.b64decode(node["data"], validate=True)
        except (ValueError, TypeError, binascii.Error) as exc:
            raise ValueError("VFS: invalid base64 file data") from exc
    elif kind == "directory":
        validate_children(node)
    else:
        raise ValueError("VFS: unknown node type")


def validate_children(node):
    """Проверить структуру каталога и рекурсивно проверить его детей."""
    if set(node) != {"type", "children"}:
        raise ValueError("VFS: directory requires type and children")
    children = node["children"]
    if not isinstance(children, dict):
        raise ValueError("VFS: children must be an object")
    for name, child in children.items():
        if not name or name in {".", ".."} or "/" in name or "\x00" in name:
            raise ValueError("VFS: invalid node name")
        validate_node(child)


def unique_object(pairs):
    """Отклонить повторяющиеся ключи JSON вместо тихой потери данных."""
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("VFS: duplicate JSON key")
        result[key] = value
    return result


class VirtualFileSystem:
    """Хранить VFS в памяти; физическая запись доступна лишь через reset."""

    def __init__(self, path):
        """Загрузить JSON без распаковки или изменения исходного файла."""
        self.path = Path(path).resolve()
        with self.path.open(encoding="utf-8-sig") as stream:
            data = json.load(stream, object_pairs_hook=unique_object)
        if not isinstance(data, dict) or set(data) != {"name", "root"}:
            raise ValueError("VFS: expected name and root")
        if not isinstance(data["name"], str) or not data["name"].strip():
            raise ValueError("VFS: name must be a nonempty string")
        validate_node(data["root"])
        if data["root"]["type"] != "directory":
            raise ValueError("VFS: root must be a directory")
        self.name = data["name"]
        self.root = data["root"]
        self.cwd = []
        self.previous = []

    def node_at(self, parts):
        """Найти узел по уже проверенным компонентам абсолютного пути."""
        node = self.root
        for part in parts:
            node = node["children"][part]
        return node

    def resolve(self, path):
        """Разрешить UNIX-путь; переход выше корня оставляет в корне."""
        if not path:
            raise ValueError("empty path")
        parts = [] if path.startswith("/") else list(self.cwd)
        for part in path.split("/"):
            node = self.node_at(parts)
            if node["type"] != "directory":
                raise ValueError(f"not a directory: {path}")
            if not part or part == ".":
                continue
            if part == "..":
                parts = parts[:-1]
                continue
            if part not in node["children"]:
                raise ValueError(f"no such file or directory: {path}")
            parts.append(part)
        return parts, self.node_at(parts)

    def change_directory(self, path):
        """Сменить каталог только после полной проверки целевого пути."""
        if path == "-":
            parts, node = self.previous, self.node_at(self.previous)
        else:
            parts, node = self.resolve(path)
        if node["type"] != "directory":
            raise ValueError(f"not a directory: {path}")
        self.previous, self.cwd = list(self.cwd), list(parts)

    def reset(self):
        """Очистить JSON и память; при ошибке записи память не менять."""
        root = directory()
        text = json.dumps({"name": self.name, "root": root}, indent=2)
        self.path.write_text(text + "\n", encoding="utf-8")
        self.root, self.cwd, self.previous = root, [], []

    def parent(self, path):
        """Найти родительский каталог и имя нового узла."""
        path = path.rstrip("/")
        parent, _, name = path.rpartition("/")
        if not name or name in {".", ".."} or "\x00" in name:
            raise ValueError("invalid target name")
        base = parent or ("/" if path.startswith("/") else ".")
        parts, node = self.resolve(base)
        if node["type"] != "directory":
            raise ValueError(f"not a directory: {base}")
        return parts, node["children"], name

    def make_directory(self, path, parents=False):
        """Создать каталог; режим -p создаёт недостающих родителей."""
        if parents:
            self.make_parents(path)
            return
        _, children, name = self.parent(path)
        if name in children:
            raise ValueError(f"file exists: {path}")
        children[name] = directory()

    def make_parents(self, path):
        """Последовательно создать компоненты пути для mkdir -p."""
        if not path:
            raise ValueError("empty path")
        parts = [] if path.startswith("/") else list(self.cwd)
        for part in path.split("/"):
            node = self.node_at(parts)
            if node["type"] != "directory":
                raise ValueError(f"not a directory: {path}")
            if not part or part == ".":
                continue
            if part == "..":
                parts = parts[:-1]
                continue
            if "\x00" in part:
                raise ValueError("invalid target name")
            node["children"].setdefault(part, directory())
            parts.append(part)
        if self.node_at(parts)["type"] != "directory":
            raise ValueError(f"not a directory: {path}")

    def copy(self, source, target, recursive=False):
        """Копировать независимое дерево, не изменяя физический JSON."""
        source_parts, source_node = self.resolve(source)
        is_directory = source_node["type"] == "directory"
        if is_directory and not recursive:
            raise ValueError("omitting directory (use -r)")
        if not source_parts:
            raise ValueError("cannot copy the VFS root")
        target_parts, children, name = self.copy_target(target, source_parts)
        full_target = target_parts + [name]
        self.check_copy(source_parts, full_target, children, name,
                        is_directory)
        children[name] = copy.deepcopy(source_node)

    def check_copy(self, source, target, children, name, is_directory):
        """Запретить само-копию и несовместимые типы назначения."""
        if target == source:
            raise ValueError("source and destination are the same")
        if is_directory and target[:len(source)] == source:
            raise ValueError("cannot copy directory into itself")
        if name in children and children[name]["type"] == "directory":
            raise ValueError("destination directory already exists")
        if is_directory and name in children:
            raise ValueError("cannot replace file with directory")

    def copy_target(self, target, source_parts):
        """Выбрать имя назначения для файла или существующего каталога."""
        try:
            parts, node = self.resolve(target)
        except ValueError:
            if target.endswith("/"):
                raise ValueError("destination directory does not exist")
            return self.parent(target)
        if node["type"] == "directory":
            return parts, node["children"], source_parts[-1]
        return self.parent(target)


def file_size(node):
    """Вернуть размер декодированных данных, а не строки base64."""
    return len(base64.b64decode(node["data"]))


def disk_usage(node, path, summary=False):
    """Посчитать байты файлов; каталоги не добавляют служебного размера."""
    if node["type"] == "file":
        size = file_size(node)
        return size, [f"{size}\t{path}"]
    total, lines = 0, []
    for name, child in sorted(node["children"].items()):
        child_path = path.rstrip("/") + "/" + name
        size, child_lines = disk_usage(child, child_path)
        total += size
        if not summary:
            lines.extend(child_lines)
    lines.append(f"{total}\t{path}")
    return total, lines
