# Gecko
# one font. zoom. word wrap. save as anything. remember session.
# tabs with close (Ctrl+W), unsaved asterisk, always at least one tab
# status bar shows live cursor coordinates (Ln X, Col Y)
# green text + green cursor + Courier New (classic terminal font)
# mascot: Gecko (Mediterranean house gecko lifestyle)
# modes: Standard (default) / Programmer (coords, syntax highlight, line numbers)
# line numbers: perfectly aligned, no top offset, no duplication on zoom

import tkinter as tk
from tkinter import filedialog, messagebox, ttk, Toplevel, Checkbutton, BooleanVar, Entry, Label, Button, StringVar
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

        # Safe icon loading
        script_dir = os.path.abspath(os.path.dirname(__file__))
        ico_path = os.path.join(script_dir, "gecko.ico")
        png_path = os.path.join(script_dir, "gecko.png")

        try:
            if os.path.exists(ico_path):
                self.root.iconbitmap(ico_path)
            else:
                icon_img = tk.PhotoImage(file=png_path)
                self.root.iconphoto(True, icon_img)
        except:
            pass

        style = ttk.Style()
        style.theme_use("default")
        style.configure("Dark.TNotebook", background="#1e1e1e", bordercolor="#1e1e1e")
        style.configure("Dark.TNotebook.Tab", background="#2d2d2d", foreground="#d4d4d4", padding=[8, 3])
        style.map("Dark.TNotebook.Tab", background=[("selected", "#1e1e1e")], foreground=[("selected", "#ffffff")])

        self.current_font_family = "Courier New"
        self.current_font_size = tk.IntVar(value=14)
        self.word_wrap = tk.BooleanVar(value=True)
        self.remember_state = tk.BooleanVar(value=True)
        self.mode_programmer = tk.BooleanVar(value=False)  # default Standard

        self.tabs = []
        self.current_tab_data = None

        self.notebook = ttk.Notebook(root, style="Dark.TNotebook")
        self.notebook.pack(fill="both", expand=True)
        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)

        self.status = tk.Label(root, text="Ln 1, Col 1", bd=1, relief=tk.SUNKEN, anchor=tk.W,
                               bg="#1e1e1e", fg="#00ff00")

        self.setup_menu()
        self.setup_shortcuts()

        self.state_path = get_state_path()
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.load_state()

        if not self.tabs:
            self.new_tab()

        self.toggle_mode()

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
        editmenu.add_command(label="Find / Replace", command=self.find_replace_dialog, accelerator="Ctrl+F")

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
        optionsmenu.add_checkbutton(label="Programmer Mode",
                                    variable=self.mode_programmer,
                                    command=self.toggle_mode)

    def setup_shortcuts(self):
        self.root.bind("<Control-t>", lambda e: self.new_tab())
        self.root.bind("<Control-o>", lambda e: self.open_file())
        self.root.bind("<Control-s>", lambda e: self.save_current())
        self.root.bind("<Control-Shift-S>", lambda e: self.save_as())
        self.root.bind("<Control-w>", lambda e: self.close_current_tab())
        self.root.bind("<Control-f>", lambda e: self.find_replace_dialog())
        self.root.bind("<Control-plus>", lambda e: self.zoom_in())
        self.root.bind("<Control-equal>", lambda e: self.zoom_in())
        self.root.bind("<Control-minus>", lambda e: self.zoom_out())

    def toggle_mode(self):
        is_programmer = self.mode_programmer.get()
        if is_programmer:
            self.status.pack(side=tk.BOTTOM, fill=tk.X)
            for tab in self.tabs:
                tab["text"].tag_configure("keyword", foreground="#ff5555")
                tab["text"].tag_configure("string", foreground="#ffff88")
                tab["text"].tag_configure("comment", foreground="#88ff88")
                self.apply_syntax_highlight(tab["text"])
                tab["text"].bind("<<Modified>>", lambda e, t=tab["text"]: self.apply_syntax_highlight(t))
                # Line numbers - rebuilt on zoom, flush alignment
                if "line_num" in tab:
                    tab["line_num"].destroy()
                line_num = tk.Text(tab["frame"], width=5, padx=3, takefocus=0, border=0,
                                   background="#1e1e1e", foreground="#666666", state="disabled",
                                   font=(self.current_font_family, self.current_font_size.get()),
                                   spacing1=0, spacing2=0, spacing3=0)
                line_num.pack(side=tk.LEFT, fill=tk.Y, before=tab["text"])
                line_num.insert("1.0", "\n".join(str(i) for i in range(1, int(tab["text"].index("end-1c").split(".")[0]) + 1)))
                line_num.config(state="disabled")
                tab["line_num"] = line_num
                self.sync_line_numbers(tab["text"], line_num)
                # Scroll sync
                def sync_scroll(*args):
                    line_num.yview(*args)
                tab["text"]['yscrollcommand'] = sync_scroll
                line_num['yscrollcommand'] = lambda first, last: tab["text"].yview_moveto(first)
                tab["text"].bind("<Configure>", lambda e, t=tab["text"], ln=line_num: self.sync_line_numbers(t, ln))
                tab["text"].bind("<MouseWheel>", lambda e, t=tab["text"], ln=line_num: self.sync_line_numbers(t, ln))
                tab["text"].bind("<KeyRelease>", lambda e, t=tab["text"], ln=line_num: self.sync_line_numbers(t, ln))
        else:
            self.status.pack_forget()
            for tab in self.tabs:
                tab["text"].tag_remove("keyword", "1.0", tk.END)
                tab["text"].tag_remove("string", "1.0", tk.END)
                tab["text"].tag_remove("comment", "1.0", tk.END)
                tab["text"].unbind("<<Modified>>")
                if "line_num" in tab:
                    tab["line_num"].destroy()
                    del tab["line_num"]
                tab["text"].unbind("<Configure>")
                tab["text"].unbind("<MouseWheel>")
                tab["text"].unbind("<KeyRelease>")
                if hasattr(tab["text"], 'yscrollcommand'):
                    tab["text"]['yscrollcommand'] = None

    def sync_line_numbers(self, text_widget, line_num_widget):
        line_num_widget.config(state="normal")
        line_num_widget.delete("1.0", tk.END)
        line_count = int(text_widget.index("end-1c").split(".")[0])
        line_num_widget.insert("1.0", "\n".join(str(i) for i in range(1, line_count + 1)))
        yview = text_widget.yview()
        line_num_widget.yview_moveto(yview[0])
        line_num_widget.config(state="disabled")

    def apply_syntax_highlight(self, text_widget):
        content = text_widget.get("1.0", tk.END)
        text_widget.tag_remove("keyword", "1.0", tk.END)
        text_widget.tag_remove("string", "1.0", tk.END)
        text_widget.tag_remove("comment", "1.0", tk.END)

        keywords = ["def", "class", "import", "from", "if", "else", "elif", "for", "while", "return", "True", "False", "None"]
        for kw in keywords:
            start = "1.0"
            while True:
                pos = text_widget.search(kw, start, stopindex=tk.END, regexp=True, exact=True)
                if not pos: break
                end = f"{pos}+{len(kw)}c"
                text_widget.tag_add("keyword", pos, end)
                start = end

        for quote in ['"', "'"]:
            start = "1.0"
            while True:
                pos = text_widget.search(quote, start, stopindex=tk.END)
                if not pos: break
                end = text_widget.search(quote, f"{pos}+1c", stopindex=tk.END)
                if end:
                    end = f"{end}+1c"
                else:
                    end = tk.END
                text_widget.tag_add("string", pos, end)
                start = end

        start = "1.0"
        while True:
            pos = text_widget.search("#", start, stopindex=tk.END)
            if not pos: break
            end = text_widget.search("\n", pos, stopindex=tk.END)
            if not end: end = tk.END
            text_widget.tag_add("comment", pos, end)
            start = end

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
        text_widget.pack(side=tk.LEFT, fill="both", expand=True)

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

        self.toggle_mode()

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
        self.toggle_mode()  # Rebuild line numbers & highlight

    def zoom_out(self):
        if self.current_font_size.get() > 6:
            self.current_font_size.set(self.current_font_size.get() - 1)
            for tab in self.tabs:
                tab["text"].configure(font=(self.current_font_family, self.current_font_size.get()))
        self.toggle_mode()

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

    def find_replace_dialog(self):
        if not self.current_tab_data:
            messagebox.showinfo("No tab", "Open or create a tab first.")
            return

        text_widget = self.current_tab_data["text"]

        dialog = Toplevel(self.root)
        dialog.title("Find / Replace")
        dialog.geometry("420x180")
        dialog.transient(self.root)
        dialog.grab_set()

        Label(dialog, text="Find what:").pack(anchor="w", padx=10, pady=(10,0))
        find_var = StringVar()
        find_entry = Entry(dialog, textvariable=find_var, width=50)
        find_entry.pack(padx=10)
        find_entry.focus_set()

        Label(dialog, text="Replace with:").pack(anchor="w", padx=10, pady=(10,0))
        replace_var = StringVar()
        replace_entry = Entry(dialog, textvariable=replace_var, width=50)
        replace_entry.pack(padx=10)

        match_case_var = BooleanVar(value=False)
        Checkbutton(dialog, text="Match case", variable=match_case_var).pack(anchor="w", padx=10, pady=5)

        def do_find():
            self.perform_find(text_widget, find_var.get(), match_case_var.get())

        def do_replace_all():
            self.perform_replace_all(text_widget, find_var.get(), replace_var.get(), match_case_var.get())

        btn_frame = tk.Frame(dialog)
        btn_frame.pack(pady=10)

        Button(btn_frame, text="Find Next", command=do_find, width=12).pack(side=tk.LEFT, padx=10)
        Button(btn_frame, text="Replace All", command=do_replace_all, width=12).pack(side=tk.LEFT, padx=10)
        Button(btn_frame, text="Close", command=dialog.destroy, width=12).pack(side=tk.LEFT, padx=10)

        dialog.bind("<Return>", lambda e: do_find())

    def perform_find(self, text_widget, find_str, match_case=False):
        if not find_str:
            return

        text_widget.tag_remove("found", "1.0", tk.END)

        pos = text_widget.search(find_str, "insert", stopindex=tk.END, nocase=(not match_case))
        if not pos:
            pos = text_widget.search(find_str, "1.0", stopindex="insert", nocase=(not match_case))
            if not pos:
                messagebox.showinfo("Find", "No more occurrences found.")
                return

        end_pos = f"{pos}+{len(find_str)}c"
        text_widget.tag_add("found", pos, end_pos)
        text_widget.tag_config("found", background="yellow", foreground="black")
        text_widget.see(pos)
        text_widget.mark_set("insert", end_pos)

    def perform_replace_all(self, text_widget, find_str, replace_str, match_case=False):
        if not find_str:
            return

        count = 0
        start_pos = "1.0"
        while True:
            pos = text_widget.search(find_str, start_pos, stopindex=tk.END, nocase=(not match_case))
            if not pos:
                break
            end_pos = f"{pos}+{len(find_str)}c"
            text_widget.delete(pos, end_pos)
            text_widget.insert(pos, replace_str)
            count += 1
            start_pos = f"{pos}+{len(replace_str)}c"

        text_widget.tag_remove("found", "1.0", tk.END)
        messagebox.showinfo("Replace", f"Replaced {count} occurrences.")

if __name__ == "__main__":
    root = tk.Tk()
    app = Gecko(root)
    root.mainloop()