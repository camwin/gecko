# Gecko text editor
# one font. zoom. word wrap. save as anything. remember session.
# tabs with close (Ctrl+W), unsaved asterisk, always at least one tab
# status bar shows live cursor coordinates (Ln X, Col Y)
# green text + green cursor + Courier New (classic terminal font)
# mascot: Gecko (Mediterranean house gecko lifestyle)

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import os
import json
from pathlib import Path
import platform

def get_state_path():
    app_name = "Gecko"
    home = Path.home()
    if platform.system() == "Windows":
        base = os.getenv("APPDATA") or home / "AppData" / "Roaming"
        return Path(base) / app_name / "state.json"
    elif platform.system() == "Darwin":
        return home / "Library" / "Application Support" / app_name / "state.json"
    else:
        base = os.getenv("XDG_CONFIG_HOME") or home / ".config"
        return Path(base) / app_name.lower() / "state.json"

class Gecko:
    def __init__(self, root):
        self.root = root
        self.root.title("Gecko")
        self.root.geometry("1000x700")
        self.root.configure(bg="#1e1e1e")

        # Safe icon loading with debug prints
        script_dir = os.path.abspath(os.path.dirname(__file__))
        ico_path = os.path.join(script_dir, "gecko.ico")
        png_path = os.path.join(script_dir, "gecko.png")

        print(f"Script directory: {script_dir}")
        print(f"gecko.ico full path: {ico_path}")
        print(f"gecko.ico exists? {os.path.exists(ico_path)}")
        print(f"gecko.png full path: {png_path}")
        print(f"gecko.png exists? {os.path.exists(png_path)}")

        icon_loaded = False

        try:
            if os.path.exists(ico_path):
                self.root.iconbitmap(ico_path)
                print("SUCCESS: Loaded gecko.ico using iconbitmap")
                icon_loaded = True
            else:
                print("gecko.ico not found")
        except tk.TclError as e:
            print(f"iconbitmap failed: {e}")

        if not icon_loaded:
            try:
                if os.path.exists(png_path):
                    icon_img = tk.PhotoImage(file=png_path)
                    self.root.iconphoto(True, icon_img)
                    print("SUCCESS: Loaded gecko.png using iconphoto fallback")
                    icon_loaded = True
                else:
                    print("gecko.png not found")
            except tk.TclError as e:
                print(f"iconphoto failed: {e}")

        if not icon_loaded:
            print("WARNING: No valid icon file found — using default feather icon")

        style = ttk.Style()
        style.theme_use("default")
        style.configure("Dark.TNotebook", background="#1e1e1e", bordercolor="#1e1e1e")
        style.configure("Dark.TNotebook.Tab", background="#2d2d2d", foreground="#d4d4d4", padding=[8, 3])
        style.map("Dark.TNotebook.Tab", background=[("selected", "#1e1e1e")], foreground=[("selected", "#ffffff")])

        self.current_font_family = "Courier New"
        self.current_font_size = tk.IntVar(value=14)
        self.word_wrap = tk.BooleanVar(value=True)
        self.remember_state = tk.BooleanVar(value=True)

        self.tabs = []
        self.current_tab_data = None

        self.notebook = ttk.Notebook(root, style="Dark.TNotebook")
        self.notebook.pack(fill="both", expand=True)
        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)

        self.status = tk.Label(root, text="Ln 1, Col 1", bd=1, relief=tk.SUNKEN, anchor=tk.W,
                               bg="#1e1e1e", fg="#00ff00")
        self.status.pack(side=tk.BOTTOM, fill=tk.X)

        self.setup_menu()
        self.setup_shortcuts()

        self.state_path = get_state_path()
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.load_state()

        if not self.tabs:
            self.new_tab()

        root.protocol("WM_DELETE_WINDOW", self.on_close)

    def setup_menu(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        filemenu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=filemenu)
        filemenu.add_command(label="New Tab", command=self.new_tab, accelerator="Ctrl+T")
        filemenu.add_command(label="Open...", command=self.open_file, accelerator="Ctrl+O")
        filemenu.add_command(label="Save", command=self.save_current, accelerator="Ctrl+S")
        filemenu.add_command(label="Save As...", command=self.save_as, accelerator="Ctrl+Shift+S")
        filemenu.add_separator()
        filemenu.add_command(label="Close Tab", command=self.close_current_tab, accelerator="Ctrl+W")

        editmenu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Edit", menu=editmenu)
        editmenu.add_command(label="Undo", command=lambda: self.get_current_text().edit_undo() if self.get_current_text() else None, accelerator="Ctrl+Z")
        editmenu.add_command(label="Redo", command=lambda: self.get_current_text().edit_redo() if self.get_current_text() else None, accelerator="Ctrl+Y")

        viewmenu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="View", menu=viewmenu)
        viewmenu.add_command(label="Zoom In", command=self.zoom_in, accelerator="Ctrl++")
        viewmenu.add_command(label="Zoom Out", command=self.zoom_out, accelerator="Ctrl+-")
        viewmenu.add_checkbutton(label="Word Wrap", variable=self.word_wrap, command=self.update_wrap)

        optionsmenu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Options", menu=optionsmenu)
        optionsmenu.add_checkbutton(label="Remember last session",
                                    variable=self.remember_state,
                                    command=self.save_state)

    def setup_shortcuts(self):
        self.root.bind("<Control-t>", lambda e: self.new_tab())
        self.root.bind("<Control-o>", lambda e: self.open_file())
        self.root.bind("<Control-s>", lambda e: self.save_current())
        self.root.bind("<Control-Shift-S>", lambda e: self.save_as())
        self.root.bind("<Control-w>", lambda e: self.close_current_tab())
        self.root.bind("<Control-plus>", lambda e: self.zoom_in())
        self.root.bind("<Control-equal>", lambda e: self.zoom_in())
        self.root.bind("<Control-minus>", lambda e: self.zoom_out())

    def get_current_text(self):
        return self.current_tab_data["text"] if self.current_tab_data else None

    def update_cursor_position(self):
        if not self.current_tab_data:
            return
        text = self.current_tab_data["text"]
        pos = text.index("insert")
        line, col = pos.split('.')
        self.status.config(text=f"Ln {line}, Col {int(col)+1}")

    def new_tab(self, title="Untitled", content="", path=None):
        tab_frame = tk.Frame(self.notebook, bg="#1e1e1e")
        text_widget = tk.Text(tab_frame,
                              wrap=tk.WORD if self.word_wrap.get() else tk.NONE,
                              font=(self.current_font_family, self.current_font_size.get()),
                              undo=True,
                              bg="#1e1e1e",
                              fg="#00ff00",
                              insertbackground="#00ff00",
                              insertwidth=5,
                              padx=15, pady=15)
        text_widget.pack(fill="both", expand=True)

        self.notebook.add(tab_frame, text=title)

        tab_info = {"frame": tab_frame, "text": text_widget, "path": path, "title": title}
        self.tabs.append(tab_info)
        self.notebook.select(tab_frame)
        self.current_tab_data = tab_info

        if content:
            text_widget.insert("1.0", content)
        text_widget.edit_modified(False)

        def force_focus():
            text_widget.focus_force()
            text_widget.mark_set("insert", "end")
            text_widget.see("end")
            self.update_cursor_position()
        self.root.after(0, force_focus)
        self.root.after(10, force_focus)
        self.root.after(100, force_focus)

        text_widget.bind("<KeyRelease>", lambda e: self.update_cursor_position())
        text_widget.bind("<ButtonRelease-1>", lambda e: self.update_cursor_position())
        text_widget.bind("<<Modified>>", lambda e: self.update_tab_title(tab_info))

    def on_tab_changed(self, event):
        selected = self.notebook.select()
        if not selected: return
        for tab in self.tabs:
            if str(tab["frame"]) == selected:
                self.current_tab_data = tab
                def force_focus():
                    tab["text"].focus_force()
                    tab["text"].mark_set("insert", "end")
                    tab["text"].see("end")
                    self.update_cursor_position()
                self.root.after(0, force_focus)
                self.root.after(10, force_focus)
                break

    def update_tab_title(self, tab):
        prefix = "*" if tab["text"].edit_modified() else ""
        name = Path(tab["path"]).name if tab["path"] else tab["title"]
        self.notebook.tab(tab["frame"], text=prefix + name)

    def zoom_in(self):
        self.current_font_size.set(self.current_font_size.get() + 1)
        for tab in self.tabs:
            tab["text"].configure(font=(self.current_font_family, self.current_font_size.get()))

    def zoom_out(self):
        if self.current_font_size.get() > 6:
            self.current_font_size.set(self.current_font_size.get() - 1)
            for tab in self.tabs:
                tab["text"].configure(font=(self.current_font_family, self.current_font_size.get()))

    def update_wrap(self):
        mode = tk.WORD if self.word_wrap.get() else tk.NONE
        for tab in self.tabs:
            tab["text"].configure(wrap=mode)

    def open_file(self):
        path = filedialog.askopenfilename(filetypes=[("All files", "*.*"), ("Text", "*.txt"), ("Python", "*.py")])
        if path:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                self.new_tab(title=Path(path).name, content=content, path=path)
            except Exception as e:
                messagebox.showerror("Error", f"Could not open\n{e}")

    def save_current(self):
        if not self.current_tab_data: return
        if self.current_tab_data["path"]:
            self.save_to_path(self.current_tab_data["path"])
        else:
            self.save_as()

    def save_as(self):
        path = filedialog.asksaveasfilename(defaultextension=".txt")
        if path:
            self.save_to_path(path)
            self.current_tab_data["path"] = path
            self.update_tab_title(self.current_tab_data)

    def save_to_path(self, path):
        try:
            content = self.current_tab_data["text"].get("1.0", tk.END).rstrip()
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            self.current_tab_data["text"].edit_modified(False)
            self.update_tab_title(self.current_tab_data)
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def close_current_tab(self):
        if not self.current_tab_data: return
        idx = self.notebook.index("current")
        if self.current_tab_data["text"].edit_modified():
            if not messagebox.askyesno("Unsaved Changes", "Close anyway?"):
                return
        self.notebook.forget(idx)
        self.tabs.pop(idx)
        if self.tabs:
            self.notebook.select(self.tabs[-1]["frame"])
            self.current_tab_data = self.tabs[-1]
        else:
            self.new_tab()

    def save_state(self):
        if not self.remember_state.get():
            if self.state_path.exists():
                self.state_path.unlink()
            return
        data = {"tabs": []}
        for tab in self.tabs:
            data["tabs"].append({
                "path": str(tab["path"]) if tab["path"] else None,
                "content": tab["text"].get("1.0", tk.END).rstrip() if not tab["path"] else None
            })
        try:
            with open(self.state_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except: pass

    def load_state(self):
        if not self.remember_state.get() or not self.state_path.exists(): return
        try:
            with open(self.state_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for t in data.get("tabs", []):
                if t.get("path") and Path(t["path"]).exists():
                    with open(t["path"], "r", encoding="utf-8") as f:
                        self.new_tab(title=Path(t["path"]).name, content=f.read(), path=t["path"])
                elif t.get("content"):
                    self.new_tab(content=t["content"])
        except: pass

    def on_close(self):
        self.save_state()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = Gecko(root)
    root.mainloop()