import tkinter as tk

root = tk.Tk()
root.title("Shell Emulator — MyVFS")
root.geometry("800x500")

#оздаём область для вывода
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


def process_input(event):
    """Обработать введённую пользователем команду."""
    global last_status
    command_line = command_entry.get()
    command_entry.delete(0, tk.END)
    if command_line.strip() == "":
        return
    output.config(state=tk.NORMAL)
    output.insert(tk.END, f"localhost:~# {command_line}\n")
    parts = command_line.strip().split()
    command = parts[0]
    arguments = parts[1:]
    if command == "ls":
        output.insert(tk.END, "Command: ls\n")
        output.insert(tk.END, f"Arguments: {arguments}\n")
        last_status = 0
    elif command == "cd":
        if len(arguments) > 1:
            output.insert(tk.END, "cd: too many arguments\n")
            last_status = 1
        else:
            output.insert(tk.END, "Command: cd\n")
            output.insert(tk.END, f"Arguments: {arguments}\n")
            last_status = 0
    elif command == "exit":
        if len(arguments) > 0:
            output.insert(tk.END, "exit: too many arguments\n")
            last_status = 1
        else:
            output.insert(tk.END, "exit\n")
            last_status = 0
            root.after(100, root.destroy)
    else:
        output.insert(tk.END, f"sh: {command}: not found\n")
        last_status = 127
    output.see(tk.END)
    output.config(state=tk.DISABLED)


command_entry.bind("<Return>", process_input)

root.mainloop()
