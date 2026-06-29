import tkinter as tk
from tkinter import scrolledtext
import requests
import json
import ctypes

root = tk.Tk()
root.title("bot")
root.geometry("600x600")

chat = scrolledtext.ScrolledText(root, height=18, font=("Consolas", 11))
chat.pack(fill=tk.BOTH, expand=True)

entry = tk.Text(root, height=5, font=("Consolas", 11))
entry.pack(fill=tk.X)

def _right_click(event):
    menu = tk.Menu(root, tearoff=0)
    menu.add_command(label="复制", command=lambda: root.clipboard_append(event.widget.selection_get() if event.widget.selection_get() else ""))
    menu.add_command(label="粘贴", command=lambda: event.widget.insert(tk.INSERT, root.clipboard_get()))
    menu.post(event.x_root, event.y_root)

def send(e=None):
    cmd = entry.get("1.0", tk.END).strip()
    if cmd:
        chat.delete("1.0", tk.END)
        if cmd.startswith("@"):
            cmd = cmd[1:].strip()
        try:
            resp = requests.post(
                "http://127.0.0.1:5000/api/desktop",
                json={"command": cmd},
                timeout=10
            )
            if resp.ok:
                data = resp.json()
                if data.get("success"):
                    chat.insert(tk.END, "✅ " + str(data.get("data", "ok")) + "\n\n")
                else:
                    chat.insert(tk.END, "❌ " + str(data.get("error", "")) + "\n\n")
            else:
                chat.insert(tk.END, "❌ HTTP " + str(resp.status_code) + "\n\n")
        except Exception as e:
            chat.insert(tk.END, "❌ 无法连接: " + str(e) + "\n\n")
        entry.delete("1.0", tk.END)
        chat.see(tk.END)

entry.bind("<Return>", send)
entry.bind("<Button-3>", _right_click)
chat.bind("<Button-3>", _right_click)

ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)
root.mainloop()