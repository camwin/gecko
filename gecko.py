# Gecko
# one font. zoom. word wrap. save as anything. remember session.
# tabs with close (Ctrl+W), unsaved asterisk, always at least one tab
# status bar shows live cursor coordinates (Ln X, Col Y)
# green text + green cursor + Courier New (classic terminal font)
# mascot: Gecko (Mediterranean house gecko lifestyle)
# modes: Standard (default) / Programmer (coords, syntax highlight, line numbers)
# find/replace: single dialog, replace optional, match case toggle
# auto-highlight matches on selection (yellow)

import tkinter as tk
from tkinter import filedialog, messagebox, ttk, Toplevel, Checkbutton, BooleanVar, Entry, Label, Button, StringVar
import os
import json
from pathlib import Path
import platform
from pygments import lex
from pygments.lexers import get_lexer_by_name, get_lexer_for_filename
from pygments.styles import get_style_by_name
from pygments.util import ClassNotFound
from pygments.token import Text as PygmentsText
from tkinterdnd2 import DND_FILES, TkinterDnD

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

        # Create a simple 'X' image for the close button
        self.close_img = tk.PhotoImage(width=14, height=14)
        # Draw an X in light gray
        for i in range(3, 11):
            self.close_img.put("#aaaaaa", (i, i))
            self.close_img.put("#aaaaaa", (i, 13-i))
            self.close_img.put("#aaaaaa", (i+1, i))      # Thickens
            self.close_img.put("#aaaaaa", (i+1, 13-i))   # Thicken

        style = ttk.Style()
        style.theme_use("default")
        style.element_create("close", "image", self.close_img, border=0, sticky="")

        style.configure("Dark.TNotebook", background="#1e1e1e", bordercolor="#1e1e1e")
        style.configure("Dark.TNotebook.Tab", background="#2d2d2d", foreground="#d4d4d4", padding=[10, 2])
        style.map("Dark.TNotebook.Tab", background=[("selected", "#1e1e1e")], foreground=[("selected", "#ffffff")])

        style.layout("Dark.TNotebook.Tab", [
            ("Notebook.tab", {
                "sticky": "nswe",
                "children": [
                    ("Notebook.padding", {
                        "side": "top", "sticky": "nswe",
                        "children": [
                            ("Notebook.focus", {
                                "side": "top", "sticky": "nswe",
                                "children": [
                                    ("Notebook.label", {"side": "left", "sticky": ""}),
                                    ("Notebook.close", {"side": "left", "sticky": ""}),
                                ]
                            })
                        ]
                    })
                ]
            })
        ])

        self.current_font_family = "Courier New"
        self.current_font_size = tk.IntVar(value=14)
        self.word_wrap = tk.BooleanVar(value=True)
        self.remember_state = tk.BooleanVar(value=True)
        self.mode_programmer = tk.BooleanVar(value=False)  # default Standard
        self.current_syntax_var = tk.StringVar(value="Plain Text")
        self.recent_files = []

        # Pygments setup
        self.pygments_style_name = 'monokai'
        self.pygments_style = get_style_by_name(self.pygments_style_name)
        self.default_fg = self.pygments_style.style_for_token(PygmentsText).get('color') or "d4d4d4"

        self.tabs = []
        self.current_tab_data = None

        self.notebook = ttk.Notebook(root, style="Dark.TNotebook")
        self.notebook.pack(fill="both", expand=True)
        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)
        self.notebook.bind("<Button-1>", self.on_tab_click)
        self.notebook.bind("<Double-Button-1>", self.on_tab_double_click)

        self.status = tk.Frame(root, bg="#1e1e1e", bd=1, relief=tk.SUNKEN)
        self.status.pack(side=tk.BOTTOM, fill=tk.X)
        self.status_cursor = tk.Label(self.status, text="Ln 1, Col 1", bg="#1e1e1e", fg="#00ff00", anchor=tk.W)
        self.status_cursor.pack(side=tk.LEFT, padx=5)
        self.status_syntax = tk.Label(self.status, text="Plain Text", bg="#1e1e1e", fg="#00ff00", anchor=tk.E)
        self.status_syntax.pack(side=tk.RIGHT, padx=5)

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
        self.menubar = tk.Menu(self.root)
        self.root.config(menu=self.menubar)

        filemenu = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="File", menu=filemenu)
        filemenu.add_command(label="New Tab", command=self.new_tab, accelerator="Ctrl+T")
        filemenu.add_command(label="Open...", command=self.open_file, accelerator="Ctrl+O")
        self.recent_menu = tk.Menu(filemenu, tearoff=0)
        filemenu.add_cascade(label="Open Recent", menu=self.recent_menu)
        filemenu.add_command(label="Save", command=self.save_current, accelerator="Ctrl+S")
        filemenu.add_command(label="Save As...", command=self.save_as, accelerator="Ctrl+Shift+S")
        filemenu.add_separator()
        filemenu.add_command(label="Close Tab", command=self.close_tab, accelerator="Ctrl+W")

        editmenu = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="Edit", menu=editmenu)
        editmenu.add_command(label="Undo", command=lambda: self.get_current_text().edit_undo() if self.get_current_text() else None, accelerator="Ctrl+Z")
        editmenu.add_command(label="Redo", command=lambda: self.get_current_text().edit_redo() if self.get_current_text() else None, accelerator="Ctrl+Y")
        editmenu.add_command(label="Find / Replace", command=self.find_replace_dialog, accelerator="Ctrl+F")

        viewmenu = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="View", menu=viewmenu)
        viewmenu.add_command(label="Zoom In", command=self.zoom_in, accelerator="Ctrl++")
        viewmenu.add_command(label="Zoom Out", command=self.zoom_out, accelerator="Ctrl+-")
        viewmenu.add_checkbutton(label="Word Wrap", variable=self.word_wrap, command=self.update_wrap)

        self.syntaxmenu = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="Syntax", menu=self.syntaxmenu)
        self.syntaxmenu.add_radiobutton(label="Plain Text", variable=self.current_syntax_var, value="Plain Text", command=lambda: self.set_current_tab_lexer('plaintext'))
        self.syntaxmenu.add_command(label="Auto-detect", command=lambda: self.set_current_tab_lexer('auto'))
        self.syntaxmenu.add_separator()

        common_languages = ['Python', 'JavaScript', 'HTML', 'CSS', 'JSON', 'SQL', 'XML', 'Markdown', 'YAML', 'Bash']
        for lang in sorted(common_languages):
            try:
                lexer_info = get_lexer_by_name(lang.lower())
                alias = lexer_info.aliases[0]
                self.syntaxmenu.add_radiobutton(label=lang, variable=self.current_syntax_var, value=lang, command=lambda a=alias: self.set_current_tab_lexer(a))
            except ClassNotFound:
                continue

        optionsmenu = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="Options", menu=optionsmenu)
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
        self.root.bind("<Control-w>", lambda e: self.close_tab())
        self.root.bind("<Control-f>", lambda e: self.find_replace_dialog())
        self.root.bind("<Control-plus>", lambda e: self.zoom_in())
        self.root.bind("<Control-equal>", lambda e: self.zoom_in())
        self.root.bind("<Control-minus>", lambda e: self.zoom_out())

        self.root.drop_target_register(DND_FILES)
        self.root.dnd_bind('<<Drop>>', self.on_drop)

    def toggle_mode(self):
        is_programmer = self.mode_programmer.get()

        try:
            self.menubar.index("Syntax")
            has_syntax = True
        except tk.TclError:
            has_syntax = False

        if is_programmer:
            if not has_syntax:
                try:
                    self.menubar.insert_cascade("Options", label="Syntax", menu=self.syntaxmenu)
                except tk.TclError:
                    self.menubar.add_cascade(label="Syntax", menu=self.syntaxmenu)
            self.status.pack(side=tk.BOTTOM, fill=tk.X)
        else:
            if has_syntax:
                self.menubar.delete("Syntax")
            self.status.pack_forget()

        for tab in self.tabs:
            if is_programmer:
                if "line_num" not in tab:
                    line_num = tk.Text(tab["frame"], width=5, padx=3, takefocus=0, border=0,
                                       background="#1e1e1e", foreground="#666666", state="disabled",
                                       font=(self.current_font_family, self.current_font_size.get()),
                                       spacing1=0, spacing2=0, spacing3=0, pady=15)
                    tab["line_num"] = line_num
                    tab["text"].bind("<Configure>", lambda e, t=tab["text"], ln=tab["line_num"]: self.sync_line_numbers(t, ln), add='+')
                    tab["text"].bind("<KeyRelease>", lambda e, t=tab["text"], ln=tab["line_num"]: self.sync_line_numbers(t, ln), add='+')
                    tab["text"].bind("<MouseWheel>", lambda e, t=tab["text"], ln=tab["line_num"]: self.sync_line_numbers(t, ln), add='+')

                tab["line_num"].pack(side=tk.LEFT, fill=tk.Y, before=tab["text"])
                self.sync_line_numbers(tab["text"], tab["line_num"])
                self.apply_pygments_highlight(tab)
            else:
                if "line_num" in tab:
                    tab["line_num"].pack_forget()
                self._clear_highlighting(tab)

    def sync_line_numbers(self, text_widget, line_num_widget):
        line_num_widget.configure(font=(self.current_font_family, self.current_font_size.get()))
        line_num_widget.config(state="normal")
        line_num_widget.delete("1.0", tk.END)
        line_count = int(text_widget.index("end-1c").split(".")[0])
        line_num_widget.insert("1.0", "\n".join(str(i) for i in range(1, line_count + 1)))
        yview = text_widget.yview()
        line_num_widget.yview_moveto(yview[0])
        line_num_widget.config(state="disabled")

    def get_current_text(self):
        return self.current_tab_data["text"] if self.current_tab_data else None

    def update_cursor_position(self):
        if not self.current_tab_data:
            return
        text = self.current_tab_data["text"]
        pos = text.index("insert")
        line, col = pos.split('.')
        self.status_cursor.config(text=f"Ln {line}, Col {int(col)+1}")

    def new_tab(self, title="Untitled", content="", path=None, lexer=None):
        tab_frame = tk.Frame(self.notebook, bg="#1e1e1e")
        text_widget = tk.Text(tab_frame,
                              wrap=tk.WORD if self.word_wrap.get() else tk.NONE,
                              font=(self.current_font_family, self.current_font_size.get()),
                              undo=True,
                              bg="#1e1e1e",
                              fg=f"#{self.default_fg}",
                              insertbackground="#00ff00",
                              insertwidth=5,
                              padx=15, pady=15)
        text_widget.pack(fill="both", expand=True)

        self.notebook.add(tab_frame, text=title)

        # Configure pygments tags for this widget
        for token, style in self.pygments_style:
            tag_name = f"pyg_{str(token)}"
            fg = style.get('color')
            if fg:
                text_widget.tag_configure(tag_name, foreground=f"#{fg}")

        tab_info = {"frame": tab_frame, "text": text_widget, "path": path, "title": title, "lexer": lexer, "highlight_job": None}
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
        text_widget.bind("<<Modified>>", lambda e, t=tab_info: (self.update_tab_title(t), self.schedule_highlight(t)))

        # Auto-highlight on selection
        text_widget.bind("<<Selection>>", lambda e, t=text_widget: self.auto_highlight_matches(t))

        self.toggle_mode()

    def auto_highlight_matches(self, text_widget):
        text_widget.tag_remove("auto_match", "1.0", tk.END)

        try:
            sel_start = text_widget.index("sel.first")
            sel_end = text_widget.index("sel.last")
            selected_text = text_widget.get(sel_start, sel_end).strip()
            if not selected_text or len(selected_text) < 2:
                return

            start_pos = "1.0"
            while True:
                pos = text_widget.search(selected_text, start_pos, stopindex=tk.END, nocase=True, exact=True)
                if not pos:
                    break
                end_pos = f"{pos}+{len(selected_text)}c"
                if pos == sel_start:
                    start_pos = end_pos
                    continue
                text_widget.tag_add("auto_match", pos, end_pos)
                start_pos = end_pos

            text_widget.tag_config("auto_match", background="#444400", foreground="#ffff88")
        except tk.TclError:
            pass

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
                self.update_syntax_ui()
                break

    def update_tab_title(self, tab):
        prefix = "*" if tab["text"].edit_modified() else ""
        name = Path(tab["path"]).name if tab["path"] else tab["title"]
        self.notebook.tab(tab["frame"], text=prefix + name)

    def zoom_in(self):
        self.current_font_size.set(self.current_font_size.get() + 1)
        for tab in self.tabs:
            tab["text"].configure(font=(self.current_font_family, self.current_font_size.get()))
        self.toggle_mode()

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
            self.open_path(path)

    def open_path(self, path):
        if not path or not os.path.isfile(path):
            if path in self.recent_files:
                self.recent_files.remove(path)
                self.update_recent_menu()
            return

        self.add_to_recent(path)

        # Check if file is already open
        for tab in self.tabs:
            if tab["path"] and Path(tab["path"]).resolve() == Path(path).resolve():
                self.notebook.select(tab["frame"])
                return

        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            try:
                lexer = get_lexer_for_filename(path, stripall=True)
            except ClassNotFound:
                lexer = None

            self.new_tab(title=Path(path).name, content=content, path=path, lexer=lexer)

            if str(path).lower().endswith(('.py', '.go')):
                if not self.mode_programmer.get():
                    self.mode_programmer.set(True)
                    self.toggle_mode()
        except Exception as e:
            messagebox.showerror("Error", f"Could not open file\n{e}")

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
            self.add_to_recent(path)
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def close_tab(self, index=None):
        if index is None:
            if not self.tabs: return
            index = self.notebook.index("current")
        
        if index < 0 or index >= len(self.tabs):
            return

        tab_to_close = self.tabs[index]
        
        if tab_to_close["text"].edit_modified():
            self.notebook.select(index) # Show tab to user
            if not messagebox.askyesno("Unsaved Changes", f"Close '{tab_to_close['title']}' without saving?"):
                return

        self.notebook.forget(index)
        self.tabs.pop(index)
        
        if not self.tabs:
            self.new_tab()
        # If tabs remain, notebook automatically selects the next appropriate one

    def save_state(self):
        if not self.remember_state.get():
            if self.state_path.exists():
                self.state_path.unlink()
            return
        data = {"tabs": [], "recent_files": self.recent_files}
        for tab in self.tabs:
            content = None
            if not tab["path"] or tab["text"].edit_modified():
                content = tab["text"].get("1.0", "end-1c")
            data["tabs"].append({
                "path": str(tab["path"]) if tab["path"] else None,
                "content": content
            })
        try:
            with open(self.state_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except: pass

    def load_state(self):
        if not self.remember_state.get() or not self.state_path.exists(): return
        should_be_programmer_mode = False
        try:
            with open(self.state_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.recent_files = data.get("recent_files", [])
            self.update_recent_menu()
            for t in data.get("tabs", []):
                path = t.get("path")
                content = t.get("content")
                if path and Path(path).exists():
                    if str(path).lower().endswith(('.py', '.go')):
                        should_be_programmer_mode = True
                    try:
                        lexer = get_lexer_for_filename(path, stripall=True)
                    except ClassNotFound:
                        lexer = None
                    if content is not None:
                        self.new_tab(title=Path(path).name, content=content, path=path, lexer=lexer)
                        self.current_tab_data["text"].edit_modified(True)
                        self.update_tab_title(self.current_tab_data)
                    else:
                        with open(path, "r", encoding="utf-8") as f:
                            self.new_tab(title=Path(path).name, content=f.read(), path=path, lexer=lexer)
                elif content:
                    self.new_tab(content=content)
                    self.current_tab_data["text"].edit_modified(True)
                    self.update_tab_title(self.current_tab_data)

            if should_be_programmer_mode:
                self.mode_programmer.set(True)
        except: pass

    def on_close(self):
        self.save_state()
        self.root.destroy()

    def add_to_recent(self, path):
        if not path: return
        path = str(Path(path).resolve())
        if path in self.recent_files:
            self.recent_files.remove(path)
        self.recent_files.insert(0, path)
        self.recent_files = self.recent_files[:10]
        self.update_recent_menu()

    def update_recent_menu(self):
        self.recent_menu.delete(0, tk.END)
        for path in self.recent_files:
            self.recent_menu.add_command(label=path, command=lambda p=path: self.open_path(p))
        if self.recent_files:
            self.recent_menu.add_separator()
            self.recent_menu.add_command(label="Clear Recently Opened", command=self.clear_recent)

    def clear_recent(self):
        self.recent_files = []
        self.update_recent_menu()

    def set_current_tab_lexer(self, lexer_name):
        if not self.current_tab_data:
            return

        lexer = None
        try:
            if lexer_name == 'auto':
                if self.current_tab_data.get('path'):
                    lexer = get_lexer_for_filename(self.current_tab_data['path'], stripall=True)
            elif lexer_name != 'plaintext':
                lexer = get_lexer_by_name(lexer_name, stripall=True)
        except ClassNotFound:
            lexer = None

        self.current_tab_data['lexer'] = lexer
        self.apply_pygments_highlight(self.current_tab_data)
        self.update_syntax_ui()

    def update_syntax_ui(self):
        if not self.current_tab_data: return
        lexer = self.current_tab_data.get("lexer")
        name = lexer.name if lexer else "Plain Text"
        self.current_syntax_var.set(name)
        self.status_syntax.config(text=name)

    def schedule_highlight(self, tab_info):
        if not self.mode_programmer.get():
            return
        if tab_info.get("highlight_job"):
            self.root.after_cancel(tab_info["highlight_job"])
        tab_info["highlight_job"] = self.root.after(300, lambda: self.apply_pygments_highlight(tab_info))

    def apply_pygments_highlight(self, tab_info):
        if not self.mode_programmer.get() or not tab_info or not tab_info.get('lexer'):
            self._clear_highlighting(tab_info)
            return

        text_widget = tab_info["text"]
        lexer = tab_info["lexer"]
        content = text_widget.get("1.0", tk.END)

        self._clear_highlighting(tab_info)

        start_index = "1.0"
        for token, text in lex(content, lexer):
            end_index = f"{start_index}+{len(text)}c"
            tag_name = f"pyg_{str(token)}"
            # Only add the tag if it's been configured (i.e., has a color)
            if text_widget.tag_cget(tag_name, "foreground"):
                text_widget.tag_add(tag_name, start_index, end_index)
            start_index = end_index

    def _clear_highlighting(self, tab_info):
        if not tab_info: return
        text_widget = tab_info["text"]
        for tag in text_widget.tag_names():
            if tag.startswith("pyg_"):
                text_widget.tag_remove(tag, "1.0", tk.END)

    def on_drop(self, event):
        try:
            files = self.root.tk.splitlist(event.data)
            for f in files:
                self.open_path(f)
        except Exception as e:
            messagebox.showerror("Drop Error", f"Could not handle dropped file(s):\n{e}")

    def on_tab_click(self, event):
        try:
            if self.notebook.identify(event.x, event.y) == "close":
                index = self.notebook.index(f"@{event.x},{event.y}")
                self.close_tab(index)
        except tk.TclError:
            pass

    def on_tab_double_click(self, event):
        if not self.notebook.identify(event.x, event.y):
            self.new_tab()

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
    root = TkinterDnD.Tk()
    app = Gecko(root)
    root.mainloop()