"""Графический прототип командной оболочки: этап 1, вариант 10."""

import tkinter as tk

MAX_CD_ARGUMENTS = 1

root = tk.Tk()
root.title("Shell Emulator — MyVFS")
root.geometry("800x500")

output = tk.Text(
    root,
    bg="#000000",
    fg="white",
    font=("Consolas", 12),
    state=tk.DISABLED,
)
output.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

input_frame = tk.Frame(root, bg="#000000")
input_frame.pack(fill=tk.X, padx=10, pady=(0, 30))

prompt = tk.Label(
    input_frame,
    text="localhost:~# ",
    bg="#1e1e1e",
    fg="#00ff00",
    font=("Consolas", 12),
)
prompt.pack(side=tk.LEFT)

command_entry = tk.Entry(
    input_frame,
    bg="#2d2d2d",
    fg="white",
    insertbackground="white",
    font=("Consolas", 12),
)
command_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

last_status = 0


def execute_command(command, arguments):
    """Выполнить заглушку и вернуть статус, текст и признак exit."""
    if command == "ls":
        return 0, f"Command: ls\nArguments: {arguments}\n", False
    if command == "cd":
        if len(arguments) > MAX_CD_ARGUMENTS:
            return 1, "cd: too many arguments\n", False
        return 0, f"Command: cd\nArguments: {arguments}\n", False
    if command == "exit":
        if arguments:
            return 1, "exit: too many arguments\n", False
        return 0, "exit\n", True
    return 127, f"sh: {command}: not found\n", False


def process_input(event):
    """Разобрать строку из поля ввода и показать результат команды."""
    global last_status
    command_line = command_entry.get()
    command_entry.delete(0, tk.END)
    if command_line.strip() == "":
        return
    output.config(state=tk.NORMAL)
    output.insert(tk.END, f"localhost:~# {command_line}\n")
    parts = command_line.strip().split()
    last_status, text, should_exit = execute_command(parts[0], parts[1:])
    output.insert(tk.END, text)
    output.see(tk.END)
    output.config(state=tk.DISABLED)
    if should_exit:
        root.after(100, root.destroy)


command_entry.bind("<Return>", process_input)

root.mainloop()
